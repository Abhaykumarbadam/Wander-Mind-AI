import requests
import json

BASE = 'http://localhost:8000'


def embed():
    r = requests.post(f"{BASE}/embed_data", json={"data_dir": "./data"})
    print(r.status_code, r.text)


def ask(q: str):
    r = requests.post(f"{BASE}/ask", json={"question": q})
    print(r.status_code)
    print(json.dumps(r.json(), indent=2))


if __name__ == '__main__':
    print('Triggering embedding...')
    embed()
    print('\nSample questions:')
    ask('When is the best time to visit Paris?')
    ask('What are must-try foods in Tokyo?')
