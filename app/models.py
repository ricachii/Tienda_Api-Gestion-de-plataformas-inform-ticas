from pydantic import BaseModel, conint

class CompraIn(BaseModel):
    producto_id: conint(gt=0)
    cantidad: conint(gt=0)
