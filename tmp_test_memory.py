import json
import logging
from dotenv import load_dotenv
load_dotenv('.env')

from storage.repository import Repository
from storage.memory_manager import MemoryManager
from supervisor_agent import get_market_context, call_ai_supervisor

print('--- TEST LETTURA MEMORIA SUPERVISOR ---')
repo = Repository()
mm = MemoryManager('.')
policy = mm.read_risk_policy()
context = get_market_context(repo)

print(f'\n[Lettura File] Policy Attuale in general_policy.md:\n{policy}')

print('\n[Interrogazione NVIDIA con policy in corso...]')
advice = call_ai_supervisor(context, risk_policy=policy)
print(f'\n[Risposta JSON da NVIDIA]:\n{json.dumps(advice, indent=2)}')

if advice and advice.get('new_insights'):
    for i in advice['new_insights']:
        print(f'\n>> [Azione] L\'IA ha deciso di aggiungere questo Insight: {i}')
        mm.append_risk_insight(i)
