import os
import logging
from pathlib import Path
from datetime import datetime, timezone

try:
    from supermemory import Supermemory
except ImportError:
    Supermemory = None

logger = logging.getLogger("storage.memory")

class MemoryManager:
    """Gestisce la memoria persistente e dinamica per gli agenti AI."""
    
    def __init__(self, project_root: str):
        self.memory_dir = Path(project_root) / "ai_memory"
        self.risk_dir = self.memory_dir / "risk"
        self.assets_dir = self.memory_dir / "assets"
        
        # New Typed Categories
        self.categories = {
            "user": self.memory_dir / "user",
            "feedback": self.memory_dir / "feedback",
            "project": self.memory_dir / "project",
            "reference": self.memory_dir / "reference"
        }
        
        self._init_dirs()
        
        # Inizializzazione Supermemory API
        api_key = os.getenv("SUPERMEMORY_API_KEY")
        if Supermemory and api_key and api_key.startswith("sm_"):
            self.sm = Supermemory(api_key=api_key)
            logger.info("✅ Supermemory Cloud Engine inizializzato (Knowledge Graph attivo).")
        else:
            self.sm = None
            logger.info("⚠️ Supermemory disabilitato (API key assente). Fallback su local files.")

    def _init_dirs(self):
        """Inizializza la struttura delle directory e inserisce memorie di default se assenti."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.risk_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        
        for p in self.categories.values():
            p.mkdir(parents=True, exist_ok=True)
            
        # Inizializza policy di rischio generale (Legacy Support)
        risk_policy = self.risk_dir / "general_policy.md"
        if not risk_policy.exists():
            with open(risk_policy, "w", encoding="utf-8") as f:
                f.write("# Risk Policy Globale\n\n- Non superare mai il budget del wallet.\n- Riduci i trade se il PnL è pesantemente in passivo.\n")

    def save_typed_memory(self, category: str, name: str, content: str, description: str = ""):
        """Salva una memoria strutturata con frontmatter YAML (Pattern da src/)."""
        if category not in self.categories:
            raise ValueError(f"Categoria non valida: {category}")
            
        path = self.categories[category] / f"{name.lower().replace(' ', '_')}.md"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        frontmatter = f"---\nname: {name}\ntype: {category}\ndescription: {description}\nlast_updated: {timestamp}\n---\n\n"
        
        # Salvataggio su supermemory (se attivo)
        if self.sm:
            try:
                # Dobbiamo combinare il tutto, supermemory accetta payload non strutturato
                sm_payload = f"Category: {category}\nContext: {description}\n\n{content}"
                self.sm.add(content=sm_payload)
                logger.info(f"Mappato ricordo nel Knowledge Graph: {name}")
            except Exception as e:
                logger.error(f"Errore sincronizzazione Supermemory: {e}")
                
        # File di fallback locale
        with open(path, "w", encoding="utf-8") as f:
            f.write(frontmatter + content)

    def get_typed_context(self, category: str) -> str:
        """Aggrega tutte le memorie di una categoria in un unico blocco di testo per l'IA."""
        if category not in self.categories:
            return ""
            
        # Retrieval intelligente da Supermemory
        if self.sm:
            try:
                # Usa query generiche per recuperare la sintesi globale
                query = f"Quali sono le tue regole operative, i tuoi insight e i tuoi feedback passati riguardo la categoria {category}?"
                response = self.sm.search.documents(q=query)
                texts = []
                if hasattr(response, "results"):
                    for r in response.results:
                        if hasattr(r, "chunks") and r.chunks:
                            for chunk in r.chunks:
                                if hasattr(chunk, "content") and chunk.content:
                                    texts.append(str(chunk.content)[:500])
                    
                if texts:
                    return "--- SUPERMEMORY KNOWLEDGE GRAPH COMPENDIUM ---\n" + "\n- ".join(texts) + "\n----------------------------------------\n"
            except Exception as e:
                # Silenzio l'errore per fallback tranquillo invece di spammare
                pass
        
        # Fallback locale originario
        context = []
        for file in self.categories[category].glob("*.md"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    context.append(f.read())
            except Exception:
                pass
        
        return "\n\n---\n\n".join(context) if context else f"Nessun dato nella categoria {category}."

    def read_risk_policy(self) -> str:
        """Legge tutte le regole e i learning di rischio cumulati dal Supervisor."""
        content = self.get_typed_context("feedback") # Mix with new system
        risk_policy = self.risk_dir / "general_policy.md"
        if risk_policy.exists():
            with open(risk_policy, "r", encoding="utf-8") as f:
                content += "\n\n# Legacy Risk Policy:\n" + f.read()
        return content

    def append_risk_insight(self, insight: str):
        """Il Supervisor aggiunge un nuovo assioma mentale imparato dagli errori/osservazioni."""
        # Now uses the structured feedback system
        self.save_typed_memory(
            category="feedback",
            name=f"risk_axiom_{datetime.now().strftime('%Y%H%M')}",
            content=insight,
            description="Insight generato automaticamente dal Risk Controller"
        )
        
        # Legacy fallback
        risk_policy = self.risk_dir / "general_policy.md"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        with open(risk_policy, "a", encoding="utf-8") as f:
            f.write(f"\n- **Insight [{timestamp}]**: {insight}\n")

    def read_asset_memory(self, asset: str) -> str:
        """Legge la memoria a lungo termine per uno specifico asset."""
        safe_asset = asset.replace("/", "").replace("\\", "")
        asset_file = self.assets_dir / f"{safe_asset}.md"
        if asset_file.exists():
            with open(asset_file, "r", encoding="utf-8") as f:
                return f.read()
        return "Nessuna memoria specifica precedente per questo asset."

    def append_asset_insight(self, asset: str, insight: str):
        """Il LiveBrain o Supervisor salva un learning formativo verso uno specifico asset."""
        safe_asset = asset.replace("/", "").replace("\\", "")
        asset_file = self.assets_dir / f"{safe_asset}.md"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        mode = "a" if asset_file.exists() else "w"
        with open(asset_file, mode, encoding="utf-8") as f:
            if mode == "w":
                f.write(f"# Asset Memory: {asset}\n")
            f.write(f"\n- **[{timestamp}]**: {insight}\n")
