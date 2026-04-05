# Tengu Companion - AI Binance Dashboard UI

Questa è la companion app del progetto `ai-binance`. Utilizza **AIRI** come frontend per renderizzare un assistente virtuale completo (V-Tuber o Chatbot testuale) che supervisiona lo stato del bot di trading. 

L'interfaccia interagirà unicamente in lettura con il motore di trading in background per salvaguardare l'esecuzione dei trade reali e ridurre impatti sulla memoria del Python locale.

## Requisiti
- Node.js / pnpm (`npm install -g pnpm`)
- Python 3.10+ (per FastAPI API)
- Uvicorn (`pip install fastapi uvicorn`)

## Avvio del Bridge (Il Cuore Backend)
Assicurarsi di aver copiato `.env.example` in `.env`.
Il bridge si occupa di esporre a AIRI i dati di SQLite e i Log in endpoint `GET`.
```bash
cd bridge-api
uvicorn main:app --port 8090
```

## Avvio di AIRI (Frontend Companion)
L'app compagna utilizza il framework AIRI per dare "animo" al bot.
```bash
cd airi
pnpm install

# Per avviare la Modalità Browser 2D/Testuale (Web)
pnpm dev

# Per avviare la Modalità Desktop App V-Tuber/Companion
pnpm dev:tamagotchi
```

## Come testare che funzioni
Dopo l'avvio, entra nella chat del Companion e chiedi in italiano:
1. "Quanto ho guadagnato oggi?"
2. "Come siamo messi con i profitti?"
3. "Ci sono trade aperti in questo momento?"
4. "Qual è il sentimento del mercato secondo te?"

AIRI capirà cosa stai chiedendo e userà magicamente l'endpoint API del Bridge per estrarre in realtime dal database i numeri reali per poi raccontarteli.
