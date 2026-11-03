"""Application settings (environment variables with the PF_ prefix)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PF_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./pharmaflow.db"

    # Warehouse rules
    tote_capacity: int = 40          # max units in one tote
    min_shelf_days: int = 90         # pharmacies do not accept stock expiring sooner

    # Simulation
    sim_autostart: bool = False      # conveyor starts moving on launch
    sim_loop: bool = True            # background tick loop (disabled in tests)
    sim_tick_seconds: float = 0.2    # real time between ticks
    sim_speed: float = 5.0           # simulated seconds per real second
    scanner_noread_rate: float = 0.03
    max_recirculations: int = 2
    manual_workers: int = 2


settings = Settings()
