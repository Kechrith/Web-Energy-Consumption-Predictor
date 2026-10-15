from datetime import datetime
from pydantic import BaseModel, Field

Temp = Field(ge=-30, le=50)       # °C
Humidity = Field(ge=0, le=100)    # %


class PredictionRequest(BaseModel):
    timestamp: datetime = Field(examples=["2016-05-10T18:00:00"])
    lights: float = Field(ge=0, description="Energy used by lights (Wh)")

    T1: float = Temp
    T2: float = Temp
    T3: float = Temp
    T4: float = Temp
    T5: float = Temp
    T6: float = Temp
    T7: float = Temp
    T8: float = Temp
    T9: float = Temp

    RH_1: float = Humidity
    RH_2: float = Humidity
    RH_3: float = Humidity
    RH_4: float = Humidity
    RH_5: float = Humidity
    RH_6: float = Humidity
    RH_7: float = Humidity
    RH_8: float = Humidity
    RH_9: float = Humidity

    T_out: float = Temp
    Press_mm_hg: float = Field(ge=600, le=850)
    RH_out: float = Humidity
    Windspeed: float = Field(ge=0)
    Visibility: float = Field(ge=0)
    Tdewpoint: float = Field(ge=-40, le=40)


class PredictionResponse(BaseModel):
    predicted_energy_wh: float
    model_name: str
    warnings: list[str]