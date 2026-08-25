"""
Sehat Saathi - Main LangChain Agent
=====================================
Orchestrates the full healthcare awareness assistant pipeline:

1. Watson Language Translator: detect language, translate to English
2. Deterministic Safety Layer: intercept red-flag keywords → emergency escalation
3. LangChain ReAct Agent:
   - RAG retrieval (WHO/MoHFW knowledge base via Chroma/FAISS)
   - Tool routing (symptom_triage, facility_locator, vaccination_schedule)
   - ConversationBufferMemory per session
4. IBM watsonx.ai Granite LLM for response generation
5. Watson Language Translator: translate response back to user's language
"""
import logging
from typing import Optional

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_core.tools import Tool
try:
    from langchain_ibm import WatsonxLLM
except ImportError:
    WatsonxLLM = None  # not available on Python 3.14 yet

from app.config import settings
from app.agent.safety_layer import check_red_flags
from app.agent.memory import get_memory
from app.multilingual.translator import translator
from app.rag.vector_store import get_retriever
from app.tools.symptom_triage import symptom_triage_tool
from app.tools.facility_locator import facility_locator_tool
from app.tools.vaccination_schedule import vaccination_schedule_tool
from app.tools.emergency_escalation import emergency_escalation_tool, get_emergency_response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sehat Saathi System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are Sehat Saathi, a multilingual AI healthcare AWARENESS assistant 
built for rural and underserved communities. You are powered by IBM watsonx.ai.

YOUR ROLE: Inform and guide — NOT diagnose or replace a doctor.

CORE RULES:
1. Use simple, everyday language. Assume the user may have low health literacy.
   Avoid medical jargon. If you must use a medical term, explain it.
2. For symptom queries: Ask up to 3 short clarifying questions BEFORE using the 
   symptom_triage_tool. Collect: duration, severity, any other symptoms.
3. When a user mentions a child's age or pregnancy stage, ALWAYS use the 
   vaccination_schedule_tool to surface the next relevant milestone, even if not asked.
4. When asked for nearby facilities, ask for location/pincode then use facility_locator_tool.
5. Ground all medical information using your knowledge tools.
6. NEVER provide specific drug names, dosages, or prescriptions.
7. End EVERY health-related response with:
   "I'm an AI assistant, not a doctor. For diagnosis or treatment, please consult a healthcare professional."
8. If uncertain, say so honestly rather than guessing.

AVAILABLE TOOLS:
- symptom_triage_tool: Assess symptoms and recommend care tier (home/doctor/urgent)
- facility_locator_tool: Find nearby PHCs, hospitals, clinics by location or pincode
- vaccination_schedule_tool: Get vaccination due dates for children or pregnant women
- emergency_escalation_tool: Get emergency helpline numbers (only use if red-flag symptoms)

IMPORTANT: You are a wellness guide, not a medical professional.

{chat_history}

Question: {input}
{agent_scratchpad}"""

# ---------------------------------------------------------------------------
# ReAct Prompt Template
# ---------------------------------------------------------------------------
REACT_PROMPT = PromptTemplate.from_template(
    """You are Sehat Saathi, an AI healthcare awareness assistant for rural communities.
Use simple language. Ground responses in WHO/MoHFW guidelines. 
Never diagnose. Never prescribe.

You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

IMPORTANT RULES:
- For symptoms: use symptom_triage_tool with a clear description of all symptoms
- For child age or pregnancy: ALWAYS use vaccination_schedule_tool proactively
- For location requests: use facility_locator_tool with pincode or city name
- End every health response with the disclaimer about consulting a healthcare professional
- Never prescribe medications or dosages

Previous conversation:
{chat_history}

Question: {input}
Thought: {agent_scratchpad}"""
)


class SehatSaathiAgent:
    """
    Main orchestrator for the Sehat Saathi healthcare assistant.
    Handles the full pipeline: translation → safety → LLM agent → translation.
    """

    def __init__(self):
        self._llm: Optional[WatsonxLLM] = None
        self._agent_executor: Optional[AgentExecutor] = None
        self._tools: list = []
        self._retriever = None
        self._initialized = False
        self._init()

    def _init(self) -> None:
        """Initialize all components."""
        try:
            self._init_llm()
            self._init_tools()
            self._init_agent()
            self._initialized = True
            logger.info("SehatSaathiAgent initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize SehatSaathiAgent: %s", e)
            raise

    def _init_llm(self) -> None:
        """Initialize IBM watsonx.ai Granite LLM."""
        logger.info("Initializing IBM watsonx.ai LLM: %s", settings.watsonx_model_id)

        if not settings.watsonx_api_key or settings.watsonx_api_key == "your_watsonx_api_key_here":
            raise ValueError(
                "WATSONX_API_KEY is not configured. Please set it in your .env file."
            )

        self._llm = WatsonxLLM(
            model_id=settings.watsonx_model_id,
            url=settings.watsonx_url,
            project_id=settings.watsonx_project_id,
            apikey=settings.watsonx_api_key,
            params={
                "decoding_method": "greedy",
                "max_new_tokens": 1024,
                "min_new_tokens": 50,
                "temperature": 0.3,
                "repetition_penalty": 1.1,
                "stop_sequences": ["Human:", "User:", "\n\nQuestion:"],
            },
        )
        logger.info("watsonx.ai LLM initialized.")

    def _init_tools(self) -> None:
        """Initialize LangChain tools with RAG-enriched descriptions."""
        logger.info("Initializing tools...")

        # Initialize RAG retriever
        try:
            self._retriever = get_retriever(k=4)
            logger.info("RAG retriever initialized.")
        except Exception as e:
            logger.warning("RAG retriever initialization failed: %s. Continuing without RAG.", e)
            self._retriever = None

        self._tools = [
            symptom_triage_tool,
            vaccination_schedule_tool,
            facility_locator_tool,
            emergency_escalation_tool,
        ]

        # If RAG is available, add it as a knowledge base tool
        if self._retriever and self._llm:
            rag_chain = RetrievalQAWithSourcesChain.from_chain_type(
                llm=self._llm,
                chain_type="stuff",
                retriever=self._retriever,
                return_source_documents=False,
            )

            def rag_query(query: str) -> str:
                """Query WHO/MoHFW knowledge base for health information."""
                try:
                    result = rag_chain({"question": query})
                    answer = result.get("answer", "")
                    sources = result.get("sources", "")
                    if sources and sources.strip():
                        return f"{answer}\n\n_Source: {sources}_"
                    return answer
                except Exception as e:
                    logger.error("RAG query failed: %s", e)
                    return "I was unable to retrieve information from the knowledge base."

            self._tools.append(
                Tool(
                    name="health_knowledge_base",
                    func=rag_query,
                    description=(
                        "Query the WHO/MoHFW health knowledge base for evidence-based information "
                        "about diseases, prevention, nutrition, and general health guidelines. "
                        "Use this for factual health questions that don't require symptom triage "
                        "or facility lookup. Input: a health question in English."
                    ),
                )
            )

        logger.info("Initialized %d tools.", len(self._tools))

    def _init_agent(self) -> None:
        """Create the LangChain ReAct agent."""
        if not self._llm:
            raise ValueError("LLM not initialized.")

        agent = create_react_agent(
            llm=self._llm,
            tools=self._tools,
            prompt=REACT_PROMPT,
        )

        self._agent_executor = AgentExecutor(
            agent=agent,
            tools=self._tools,
            verbose=True,
            max_iterations=5,
            handle_parsing_errors=True,
            return_intermediate_steps=False,
        )
        logger.info("LangChain ReAct agent created.")

    def chat(
        self,
        user_message: str,
        session_id: str = "default",
    ) -> dict:
        """
        Process a user message through the full Sehat Saathi pipeline.

        Pipeline:
        1. Translate input to English (Watson Language Translator)
        2. Check for red-flag keywords (deterministic safety layer)
        3. Run LangChain agent (RAG + tools + Granite LLM)
        4. Translate response back to user's language

        Args:
            user_message: Raw user input (any language).
            session_id: Unique session identifier for memory isolation.

        Returns:
            dict with keys:
                - response: str — assistant's reply (in user's language)
                - detected_language: str — ISO code of detected input language
                - triage_tier: Optional[int] — 1/2/3 if symptom triage ran
                - is_emergency: bool — True if red-flag was triggered
        """
        if not self._initialized or not self._agent_executor:
            raise RuntimeError("SehatSaathiAgent is not initialized.")

        logger.info("Processing message for session %s: %s...", session_id, user_message[:60])

        result = {
            "response": "",
            "detected_language": "en",
            "is_emergency": False,
            "triage_tier": None,
        }

        # --- Step 1: Language detection & translation to English ---
        english_input, detected_lang = translator.to_english(user_message)
        result["detected_language"] = detected_lang
        logger.info("Language: %s | English input: %s...", detected_lang, english_input[:60])

        # --- Step 2: Deterministic Red-Flag Safety Check ---
        is_emergency, emergency_category = check_red_flags(english_input)
        if not is_emergency:
            # Also check original text in case translation missed something
            is_emergency, emergency_category = check_red_flags(user_message)

        if is_emergency:
            result["is_emergency"] = True
            emergency_response = get_emergency_response(emergency_category)
            logger.critical(
                "EMERGENCY triggered for session %s | category: %s",
                session_id, emergency_category,
            )
            # Translate emergency response back if needed
            if detected_lang != "en":
                emergency_response = translator.from_english(emergency_response, detected_lang)
            result["response"] = emergency_response
            return result

        # --- Step 3: LangChain Agent with memory ---
        memory = get_memory(session_id, k=settings.conversation_memory_k)
        chat_history = memory.load_memory_variables({}).get("chat_history", [])

        # Format chat history for prompt
        chat_history_str = ""
        if chat_history:
            history_lines = []
            for msg in chat_history[-6:]:  # Last 3 exchanges
                if hasattr(msg, "type"):
                    prefix = "User" if msg.type == "human" else "Sehat Saathi"
                    history_lines.append(f"{prefix}: {msg.content}")
            chat_history_str = "\n".join(history_lines)

        try:
            agent_response = self._agent_executor.invoke({
                "input": english_input,
                "chat_history": chat_history_str,
            })
            english_response = agent_response.get("output", "")
        except Exception as e:
            logger.error("Agent execution failed: %s", e)
            english_response = (
                "I'm sorry, I encountered an issue processing your request. "
                "Please try again, or call the National Health Helpline at **104** "
                "for assistance.\n\n"
                "_I'm an AI assistant, not a doctor. For diagnosis or treatment, "
                "please consult a healthcare professional._"
            )

        # --- Step 4: Save to memory ---
        try:
            memory.save_context(
                {"input": user_message},
                {"output": english_response},
            )
        except Exception as e:
            logger.warning("Failed to save to memory: %s", e)

        # --- Step 5: Translate response back to user's language ---
        if detected_lang != "en":
            final_response = translator.from_english(english_response, detected_lang)
        else:
            final_response = english_response

        result["response"] = final_response
        return result


# Singleton agent instance
_agent_instance: Optional[SehatSaathiAgent] = None


def get_agent() -> SehatSaathiAgent:
    """Get or create the singleton SehatSaathiAgent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = SehatSaathiAgent()
    return _agent_instance
