import sys
sys.path.insert(0, '.')
from app.agent.mock_agent import MockSehatAgent
agent = MockSehatAgent()

questions = [
    'Why Sehat Saathi is used?',
    'What is Sehat Saathi?',
    'Tell me about Sehat Saathi',
    'Who are you?',
    'What can you do?',
    'How does Sehat Saathi work?',
    'Sehat Saathi kya hai',
    'why sehat saati will be used',
]

for q in questions:
    r = agent.chat(q, 'about_test')
    first_line = r['response'].split('\n')[0]
    is_about = 'About Sehat Saathi' in r['response'] or 'Health Companion' in r['response']
    status = 'OK  ' if is_about else 'MISS'
    print(status, '|', q[:45].ljust(45), '->', first_line[:55])
