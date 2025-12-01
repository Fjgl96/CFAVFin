# tools/schemas.py
from pydantic import BaseModel, Field
from typing import List # Usar List en lugar de list para compatibilidad con Pydantic < 2.7

# --- Schemas Pydantic ---

class BonoInput(BaseModel):
    """Schema para calcular el valor presente de un bono."""
    valor_nominal: float = Field(description="Valor nominal (facial) del bono", gt=0)
    tasa_cupon_anual: float = Field(description="Tasa de interés del cupón **ANUAL** en % (ej. 6 para 6%)", ge=0, le=100)
    tasa_descuento_anual: float = Field(description="Tasa de descuento de mercado **ANUAL** (YTM) en % (ej. 5 para 5%)", ge=0, le=100)
    num_anos: int = Field(description="Número total de **AÑOS** hasta el vencimiento (ej. 5 para 5 años)", gt=0)
    frecuencia_cupon: int = Field(description="Pagos de cupón por año (ej. 1 para anual, 2 para semestral)", gt=0)

class VANInput(BaseModel):
    """Schema para calcular el Valor Actual Neto (VAN) de un proyecto."""
    tasa_descuento: float = Field(description="Tasa de descuento (WACC, TMAR) en %", ge=0, le=100)
    inversion_inicial: float = Field(description="Desembolso inicial como un número **POSITIVO** (ej. 100000)", gt=0)
    flujos_caja: List[float] = Field(description="Lista de flujos de caja futuros (ej. [25000, 30000, 35000])")

class OpcionCallInput(BaseModel):
    """Schema para calcular el valor de una Opción Call Europea usando Black-Scholes."""
    S: float = Field(description="Precio actual del activo subyacente (Stock price)", gt=0)
    K: float = Field(description="Precio de ejercicio (Strike price)", gt=0)
    T: float = Field(description="Tiempo hasta el vencimiento en años (ej. 0.5 para 6 meses)", gt=0)
    r: float = Field(description="Tasa de interés libre de riesgo anual en %", ge=0, le=100)
    sigma: float = Field(description="Volatilidad anual del activo en % (ej. 20 para 20%)", gt=0, le=200)

class WACCInput(BaseModel):
    """Schema para calcular el Costo Promedio Ponderado de Capital (WACC)."""
    tasa_impuestos: float = Field(description="Tasa de impuestos corporativos en %", ge=0, le=100)
    costo_deuda: float = Field(description="Costo de la deuda (tasa de interés) en %", ge=0, le=100)
    costo_equity: float = Field(description="Costo del equity (capital propio) en %", ge=0, le=100)
    valor_mercado_deuda: float = Field(description="Valor de mercado total de la deuda en dólares", gt=0)
    valor_mercado_equity: float = Field(description="Valor de mercado total del equity (capital) en dólares", gt=0)

class CAPMInput(BaseModel):
    """Schema para calcular el Costo del Equity usando CAPM."""
    tasa_libre_riesgo: float = Field(description="Tasa libre de riesgo (ej. bonos del tesoro) en %", ge=0, le=100)
    beta: float = Field(description="Beta del activo (medida de volatilidad)", gt=0)
    retorno_mercado: float = Field(description="Retorno esperado del mercado (ej. S&P 500) en %", ge=0, le=100)

class SharpeRatioInput(BaseModel):
    """Schema para calcular el Ratio de Sharpe de un portafolio."""
    retorno_portafolio: float = Field(description="Retorno esperado del portafolio en %", ge=0, le=100)
    tasa_libre_riesgo: float = Field(description="Tasa libre de riesgo en %", ge=0, le=100)
    std_dev_portafolio: float = Field(description="Desviación estándar (volatilidad) del portafolio en %", gt=0, le=200)

class GordonGrowthInput(BaseModel):
    """Schema para calcular el valor de una acción usando el Modelo de Crecimiento de Gordon (DDM)."""
    dividendo_prox_periodo: float = Field(description="Dividendo esperado en el próximo periodo (D1) en dólares", gt=0)
    tasa_descuento_equity: float = Field(description="Tasa de descuento o costo del equity (Ke) en %", gt=0, le=100)
    tasa_crecimiento_dividendos: float = Field(description="Tasa de crecimiento constante de los dividendos (g) en %", ge=0, le=100)

# ========================================
# NUEVOS SCHEMAS - CFA LEVEL I
# ========================================

# --- FINANZAS CORPORATIVAS ---

class IRRInput(BaseModel):
    """Schema para calcular la Tasa Interna de Retorno (IRR)."""
    inversion_inicial: float = Field(description="Desembolso inicial como un número **POSITIVO** (ej. 100000)", gt=0)
    flujos_caja: List[float] = Field(description="Lista de flujos de caja futuros (ej. [25000, 30000, 35000])")

class PaybackPeriodInput(BaseModel):
    """Schema para calcular el Periodo de Recuperación (Payback Period)."""
    inversion_inicial: float = Field(description="Desembolso inicial como un número **POSITIVO**", gt=0)
    flujos_caja: List[float] = Field(description="Lista de flujos de caja anuales **POSITIVOS** (ej. [10000, 15000, 20000])")

class ProfitabilityIndexInput(BaseModel):
    """Schema para calcular el Índice de Rentabilidad (Profitability Index)."""
    tasa_descuento: float = Field(description="Tasa de descuento (costo de capital) en %", ge=0, le=100)
    inversion_inicial: float = Field(description="Desembolso inicial como un número **POSITIVO**", gt=0)
    flujos_caja: List[float] = Field(description="Lista de flujos de caja futuros")

# --- RENTA FIJA ---

class DurationMacaulayInput(BaseModel):
    """Schema para calcular Duration Macaulay de un bono."""
    valor_nominal: float = Field(description="Valor nominal (facial) del bono", gt=0)
    tasa_cupon_anual: float = Field(description="Tasa de interés del cupón **ANUAL** en % (ej. 6 para 6%)", ge=0, le=100)
    ytm_anual: float = Field(description="Yield to Maturity (YTM) **ANUAL** en % (ej. 5 para 5%)", ge=0, le=100)
    num_anos: int = Field(description="Número total de **AÑOS** hasta el vencimiento", gt=0)
    frecuencia_cupon: int = Field(description="Pagos de cupón por año (ej. 1 para anual, 2 para semestral)", gt=0)

class DurationModificadaInput(BaseModel):
    """Schema para calcular Duration Modificada de un bono."""
    duration_macaulay: float = Field(description="Duration Macaulay del bono (en años)", gt=0)
    ytm_anual: float = Field(description="Yield to Maturity (YTM) **ANUAL** en %", ge=0, le=100)
    frecuencia_cupon: int = Field(description="Pagos de cupón por año (ej. 1 para anual, 2 para semestral)", gt=0)

class ConvexityInput(BaseModel):
    """Schema para calcular Convexity de un bono."""
    valor_nominal: float = Field(description="Valor nominal del bono", gt=0)
    tasa_cupon_anual: float = Field(description="Tasa de cupón **ANUAL** en %", ge=0, le=100)
    ytm_anual: float = Field(description="Yield to Maturity **ANUAL** en %", ge=0, le=100)
    num_anos: int = Field(description="Años hasta el vencimiento", gt=0)
    frecuencia_cupon: int = Field(description="Pagos por año (ej. 2 para semestral)", gt=0)

class CurrentYieldInput(BaseModel):
    """Schema para calcular Current Yield de un bono."""
    pago_cupon_anual: float = Field(description="Pago de cupón anual en dólares (ej. 60 para bono con cupón 6% de $1000)", gt=0)
    precio_actual_bono: float = Field(description="Precio actual de mercado del bono en dólares", gt=0)

class BonoCuponCeroInput(BaseModel):
    """Schema para calcular el valor de un Bono Cupón Cero (Zero-Coupon Bond)."""
    valor_nominal: float = Field(description="Valor nominal (facial) al vencimiento", gt=0)
    ytm_anual: float = Field(description="Yield to Maturity **ANUAL** en %", ge=0, le=100)
    num_anos: float = Field(description="Años hasta el vencimiento (puede ser decimal ej. 2.5)", gt=0)

# --- DERIVADOS ---

class OpcionPutInput(BaseModel):
    """Schema para calcular el valor de una Opción Put Europea usando Black-Scholes."""
    S: float = Field(description="Precio actual del activo subyacente (Stock price)", gt=0)
    K: float = Field(description="Precio de ejercicio (Strike price)", gt=0)
    T: float = Field(description="Tiempo hasta el vencimiento en años (ej. 0.5 para 6 meses)", gt=0)
    r: float = Field(description="Tasa de interés libre de riesgo anual en %", ge=0, le=100)
    sigma: float = Field(description="Volatilidad anual del activo en % (ej. 20 para 20%)", gt=0, le=200)

class PutCallParityInput(BaseModel):
    """Schema para verificar Put-Call Parity."""
    precio_call: float = Field(description="Precio de la opción Call", ge=0)
    precio_put: float = Field(description="Precio de la opción Put", ge=0)
    precio_spot: float = Field(description="Precio actual del activo (S)", gt=0)
    strike: float = Field(description="Precio de ejercicio (K)", gt=0)
    tiempo_vencimiento: float = Field(description="Tiempo hasta vencimiento en años", gt=0)
    tasa_libre_riesgo: float = Field(description="Tasa libre de riesgo anual en %", ge=0, le=100)

# --- PORTAFOLIO ---

class TreynorRatioInput(BaseModel):
    """Schema para calcular el Treynor Ratio."""
    retorno_portafolio: float = Field(description="Retorno del portafolio en %", ge=-100, le=500)
    tasa_libre_riesgo: float = Field(description="Tasa libre de riesgo en %", ge=0, le=100)
    beta_portafolio: float = Field(description="Beta del portafolio (riesgo sistemático)", gt=0)

class JensenAlphaInput(BaseModel):
    """Schema para calcular Jensen's Alpha."""
    retorno_portafolio: float = Field(description="Retorno real del portafolio en %", ge=-100, le=500)
    tasa_libre_riesgo: float = Field(description="Tasa libre de riesgo en %", ge=0, le=100)
    beta_portafolio: float = Field(description="Beta del portafolio", gt=0)
    retorno_mercado: float = Field(description="Retorno del mercado en %", ge=-100, le=500)

class BetaPortafolioInput(BaseModel):
    """Schema para calcular el Beta de un portafolio de 2 activos."""
    peso_activo_1: float = Field(description="Peso del activo 1 en el portafolio (ej. 0.6 para 60%)", ge=0, le=1)
    peso_activo_2: float = Field(description="Peso del activo 2 en el portafolio (ej. 0.4 para 40%)", ge=0, le=1)
    beta_activo_1: float = Field(description="Beta del activo 1", gt=0)
    beta_activo_2: float = Field(description="Beta del activo 2", gt=0)

class RetornoPortafolioInput(BaseModel):
    """Schema para calcular el Retorno Esperado de un portafolio de 2 activos."""
    peso_activo_1: float = Field(description="Peso del activo 1 (ej. 0.6 para 60%)", ge=0, le=1)
    peso_activo_2: float = Field(description="Peso del activo 2 (ej. 0.4 para 40%)", ge=0, le=1)
    retorno_activo_1: float = Field(description="Retorno esperado del activo 1 en %", ge=-100, le=500)
    retorno_activo_2: float = Field(description="Retorno esperado del activo 2 en %", ge=-100, le=500)

class StdDevPortafolioInput(BaseModel):
    """Schema para calcular la Desviación Estándar de un portafolio de 2 activos."""
    peso_activo_1: float = Field(description="Peso del activo 1 (ej. 0.6)", ge=0, le=1)
    peso_activo_2: float = Field(description="Peso del activo 2 (ej. 0.4)", ge=0, le=1)
    std_dev_activo_1: float = Field(description="Desviación estándar del activo 1 en %", gt=0, le=200)
    std_dev_activo_2: float = Field(description="Desviación estándar del activo 2 en %", gt=0, le=200)
    correlacion: float = Field(description="Coeficiente de correlación entre los dos activos", ge=-1, le=1)

print("✅ Módulo schemas cargado.")