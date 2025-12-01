# tools/financial_tools.py
"""
Herramientas financieras con cálculos deterministas.
Actualizado con logging estructurado y manejo robusto de errores.
"""

import numpy as np
import numpy_financial as npf
from scipy.stats import norm
from langchain_core.tools import tool
from typing import List

# Importar schemas
from .schemas import (
    BonoInput, VANInput, OpcionCallInput, WACCInput,
    CAPMInput, SharpeRatioInput, GordonGrowthInput,
    # Nuevos schemas CFA Level I
    IRRInput, PaybackPeriodInput, ProfitabilityIndexInput,
    DurationMacaulayInput, DurationModificadaInput, ConvexityInput,
    CurrentYieldInput, BonoCuponCeroInput,
    OpcionPutInput, PutCallParityInput,
    TreynorRatioInput, JensenAlphaInput, BetaPortafolioInput,
    RetornoPortafolioInput, StdDevPortafolioInput
)

# Importar logger
try:
    from utils.logger import get_logger
    logger = get_logger('tools')
except ImportError:
    import logging
    logger = logging.getLogger('tools')

# ========================================
# HERRAMIENTAS FINANCIERAS
# ========================================

@tool("calcular_valor_bono", args_schema=BonoInput)
def _calcular_valor_presente_bono(
    valor_nominal: float,
    tasa_cupon_anual: float,
    tasa_descuento_anual: float,
    num_anos: int,
    frecuencia_cupon: int
) -> dict:
    """Calcula el valor presente de un bono."""
    logger.info(f"🔧 Calculando valor de bono: nominal={valor_nominal}, años={num_anos}")
    
    try:
        tasa_cupon_periodo = (tasa_cupon_anual / 100) / frecuencia_cupon
        tasa_descuento_periodo = (tasa_descuento_anual / 100) / frecuencia_cupon
        num_periodos_totales = num_anos * frecuencia_cupon
        pago_cupon = valor_nominal * tasa_cupon_periodo

        # Cálculo PV cupones
        if tasa_descuento_periodo == 0:
            pv_cupones = pago_cupon * num_periodos_totales if num_periodos_totales > 0 else 0
        elif num_periodos_totales > 0:
            pv_cupones = pago_cupon * (1 - (1 + tasa_descuento_periodo)**-num_periodos_totales) / tasa_descuento_periodo
        else:
            pv_cupones = 0

        # Cálculo PV valor nominal
        pv_nominal = valor_nominal / (1 + tasa_descuento_periodo)**num_periodos_totales if num_periodos_totales > 0 else valor_nominal

        valor_bono = pv_cupones + pv_nominal
        
        logger.info(f"✅ Valor bono calculado: ${valor_bono:,.2f}")
        return {"valor_presente_bono": round(valor_bono, 2)}
        
    except OverflowError:
        logger.error("❌ Overflow en cálculo de bono")
        return {"error": "Error de cálculo: Overflow. Verifica tasas muy grandes o periodos largos."}
    except Exception as e:
        logger.error(f"❌ Error en cálculo de bono: {type(e).__name__} - {e}")
        return {"error": f"Error calculando valor del bono: {type(e).__name__}"}


@tool("calcular_van", args_schema=VANInput)
def _calcular_van(tasa_descuento: float, inversion_inicial: float, flujos_caja: List[float]) -> dict:
    """Calcula el Valor Actual Neto (VAN) de un proyecto."""
    logger.info(f"🔧 Calculando VAN: inversión={inversion_inicial}, flujos={len(flujos_caja)}")
    
    try:
        tasa = tasa_descuento / 100
        
        if not all(isinstance(fc, (int, float)) for fc in flujos_caja):
            logger.error("❌ Flujos de caja inválidos")
            return {"error": "Los flujos de caja deben ser una lista de números."}
        
        flujos_totales = [-abs(inversion_inicial)] + flujos_caja
        van = npf.npv(tasa, flujos_totales)
        
        logger.info(f"✅ VAN calculado: ${van:,.2f}")
        return {"van": round(van, 2), "interpretacion": "Si VAN > 0, el proyecto es rentable."}
        
    except Exception as e:
        logger.error(f"❌ Error en cálculo de VAN: {type(e).__name__} - {e}")
        return {"error": f"Error calculando VAN: {type(e).__name__}"}


@tool("calcular_opcion_call", args_schema=OpcionCallInput)
def _calcular_opcion_call(S: float, K: float, T: float, r: float, sigma: float) -> dict:
    """Calcula el valor de una Opción Call Europea usando Black-Scholes."""
    logger.info(f"🔧 Calculando opción call: S={S}, K={K}, T={T}")
    
    try:
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            logger.error("❌ Parámetros inválidos en opción call")
            return {"error": "Tiempo (T), volatilidad (sigma), precio actual (S) y precio ejercicio (K) deben ser positivos."}
        
        r_dec = r / 100
        sigma_dec = sigma / 100
        
        if sigma_dec == 0:
            call_price = max(S - K * np.exp(-r_dec * T), 0)
            logger.info(f"✅ Opción call (σ=0): ${call_price:.4f}")
            return {"valor_opcion_call": round(call_price, 4)}
        
        denominator = sigma_dec * np.sqrt(T)
        d1 = (np.log(S / K) + (r_dec + 0.5 * sigma_dec**2) * T) / denominator
        d2 = d1 - denominator
        
        call_price = (S * norm.cdf(d1) - K * np.exp(-r_dec * T) * norm.cdf(d2))
        call_price = max(call_price, 0)
        
        logger.info(f"✅ Opción call calculada: ${call_price:.4f}")
        return {"valor_opcion_call": round(call_price, 4)}
        
    except OverflowError:
        logger.error("❌ Overflow en cálculo de opción")
        return {"error": "Error de cálculo: Overflow. Verifica inputs muy grandes/pequeños."}
    except ValueError as ve:
        logger.error(f"❌ Error matemático en opción: {ve}")
        return {"error": f"Error matemático: {ve}. Verifica los inputs (S, K > 0)."}
    except Exception as e:
        logger.error(f"❌ Error en cálculo de opción: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Opción Call: {type(e).__name__}"}


@tool("calcular_wacc", args_schema=WACCInput)
def _calcular_wacc(
    tasa_impuestos: float,
    costo_deuda: float,
    costo_equity: float,
    valor_mercado_deuda: float,
    valor_mercado_equity: float
) -> dict:
    """Calcula el Costo Promedio Ponderado de Capital (WACC)."""
    logger.info(f"🔧 Calculando WACC: D={valor_mercado_deuda}, E={valor_mercado_equity}")
    
    try:
        t_c = tasa_impuestos / 100
        k_d = costo_deuda / 100
        k_e = costo_equity / 100
        D = valor_mercado_deuda
        E = valor_mercado_equity
        
        if D < 0 or E < 0:
            logger.error("❌ Valores de mercado negativos")
            return {"error": "Valores de mercado de deuda y equity no pueden ser negativos."}
        
        V = D + E
        if V <= 0:
            if D==0 and E==0:
                logger.warning("⚠️ WACC = 0 (sin capital)")
                return {"wacc_porcentaje": 0.0, "nota": "WACC es 0 ya que no hay capital."}
            logger.error("❌ Valor total de mercado inválido")
            return {"error": "El valor total de mercado (Deuda + Equity) debe ser positivo."}
        
        weight_e = E / V
        weight_d = D / V
        
        wacc = weight_e * k_e + weight_d * k_d * (1 - t_c)
        
        logger.info(f"✅ WACC calculado: {wacc*100:.4f}%")
        return {"wacc_porcentaje": round(wacc * 100, 4)}
        
    except Exception as e:
        logger.error(f"❌ Error en cálculo de WACC: {type(e).__name__} - {e}")
        return {"error": f"Error calculando WACC: {type(e).__name__}"}


@tool("calcular_capm", args_schema=CAPMInput)
def _calcular_capm(tasa_libre_riesgo: float, beta: float, retorno_mercado: float) -> dict:
    """Calcula el Costo del Equity (Ke) usando el Capital Asset Pricing Model (CAPM)."""
    logger.info(f"🔧 Calculando CAPM: rf={tasa_libre_riesgo}%, β={beta}")
    
    try:
        rf = tasa_libre_riesgo / 100
        rm = retorno_mercado / 100
        k_e = rf + beta * (rm - rf)
        
        logger.info(f"✅ Ke (CAPM) calculado: {k_e*100:.4f}%")
        return {"costo_equity_porcentaje": round(k_e * 100, 4)}
        
    except Exception as e:
        logger.error(f"❌ Error en cálculo de CAPM: {type(e).__name__} - {e}")
        return {"error": f"Error calculando CAPM: {type(e).__name__}"}


@tool("calcular_sharpe_ratio", args_schema=SharpeRatioInput)
def _calcular_sharpe_ratio(retorno_portafolio: float, tasa_libre_riesgo: float, std_dev_portafolio: float) -> dict:
    """Calcula el Ratio de Sharpe para medir el retorno ajustado al riesgo."""
    logger.info(f"🔧 Calculando Sharpe Ratio: rp={retorno_portafolio}%, σ={std_dev_portafolio}%")
    
    try:
        r_p = retorno_portafolio / 100
        r_f = tasa_libre_riesgo / 100
        std_p = std_dev_portafolio / 100
        
        if std_p <= 0:
            logger.error("❌ Desviación estándar inválida")
            return {"error": "La desviación estándar del portafolio debe ser mayor que cero."}
        
        sharpe = (r_p - r_f) / std_p
        
        logger.info(f"✅ Sharpe Ratio calculado: {sharpe:.4f}")
        return {"sharpe_ratio": round(sharpe, 4)}
        
    except Exception as e:
        logger.error(f"❌ Error en cálculo de Sharpe: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Sharpe Ratio: {type(e).__name__}"}


@tool("calcular_gordon_growth", args_schema=GordonGrowthInput)
def _calcular_gordon_growth(
    dividendo_prox_periodo: float,
    tasa_descuento_equity: float,
    tasa_crecimiento_dividendos: float
) -> dict:
    """Calcula el valor de una acción usando el Modelo de Crecimiento de Gordon (DDM)."""
    logger.info(f"🔧 Calculando Gordon Growth: D1={dividendo_prox_periodo}, Ke={tasa_descuento_equity}%")
    
    try:
        D1 = dividendo_prox_periodo
        Ke = tasa_descuento_equity / 100
        g = tasa_crecimiento_dividendos / 100
        
        if D1 <= 0:
            logger.error("❌ Dividendo inválido")
            return {"error": "El dividendo del próximo periodo (D1) debe ser positivo."}
        
        if Ke <= g:
            logger.error("❌ Ke <= g (inválido para Gordon)")
            return {"error": "La tasa de descuento (Ke) debe ser estrictamente mayor que la tasa de crecimiento (g)."}
        
        denominator = Ke - g
        if denominator == 0:
            logger.error("❌ División por cero en Gordon")
            return {"error": "División por cero evitada (Ke - g es cero). Ke debe ser > g."}
        
        valor_accion = D1 / denominator
        
        if valor_accion < 0:
            logger.error("❌ Valor negativo inesperado")
            return {"error": "El cálculo resultó en un valor negativo inesperado."}
        
        logger.info(f"✅ Valor acción calculado: ${valor_accion:.2f}")
        return {"valor_intrinseco_accion": round(valor_accion, 2)}

    except Exception as e:
        logger.error(f"❌ Error en cálculo de Gordon: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Gordon Growth: {type(e).__name__}"}


# ========================================
# NUEVAS HERRAMIENTAS - CFA LEVEL I
# ========================================

# --- FINANZAS CORPORATIVAS ---

@tool("calcular_tir", args_schema=IRRInput)
def _calcular_tir(inversion_inicial: float, flujos_caja: List[float]) -> dict:
    """Calcula la Tasa Interna de Retorno (IRR) de un proyecto."""
    logger.info(f"🔧 Calculando TIR: inversión={inversion_inicial}, flujos={len(flujos_caja)}")

    try:
        if not all(isinstance(fc, (int, float)) for fc in flujos_caja):
            logger.error("❌ Flujos de caja inválidos")
            return {"error": "Los flujos de caja deben ser una lista de números."}

        # Crear flujos totales (inversión inicial negativa)
        flujos_totales = [-abs(inversion_inicial)] + flujos_caja

        # Calcular IRR usando numpy-financial
        irr = npf.irr(flujos_totales)

        if np.isnan(irr):
            logger.warning("⚠️ IRR no se pudo calcular (NaN)")
            return {"error": "No se pudo calcular el IRR. Los flujos de caja pueden no tener una solución válida."}

        irr_porcentaje = irr * 100

        logger.info(f"✅ TIR calculada: {irr_porcentaje:.4f}%")
        return {
            "tir_porcentaje": round(irr_porcentaje, 4),
            "interpretacion": f"La TIR es {irr_porcentaje:.2f}%. Si TIR > tasa de descuento, el proyecto es aceptable."
        }

    except Exception as e:
        logger.error(f"❌ Error en cálculo de TIR: {type(e).__name__} - {e}")
        return {"error": f"Error calculando TIR: {type(e).__name__}"}


@tool("calcular_payback_period", args_schema=PaybackPeriodInput)
def _calcular_payback_period(inversion_inicial: float, flujos_caja: List[float]) -> dict:
    """Calcula el Periodo de Recuperación (Payback Period) en años."""
    logger.info(f"🔧 Calculando Payback Period: inversión={inversion_inicial}")

    try:
        if not flujos_caja:
            return {"error": "Debe proporcionar al menos un flujo de caja."}

        acumulado = 0
        for i, flujo in enumerate(flujos_caja, start=1):
            acumulado += flujo
            if acumulado >= inversion_inicial:
                # Payback exacto con interpolación
                exceso_periodo_anterior = acumulado - flujo
                faltante = inversion_inicial - exceso_periodo_anterior
                fraccion_ano = faltante / flujo if flujo > 0 else 0
                payback = (i - 1) + fraccion_ano

                logger.info(f"✅ Payback Period calculado: {payback:.2f} años")
                return {
                    "payback_period_anos": round(payback, 2),
                    "interpretacion": f"El proyecto recupera la inversión en {payback:.2f} años."
                }

        # Si no se recupera la inversión
        logger.warning("⚠️ La inversión no se recupera con los flujos dados")
        return {
            "payback_period_anos": None,
            "interpretacion": "La inversión NO se recupera completamente con los flujos de caja proporcionados."
        }

    except Exception as e:
        logger.error(f"❌ Error en cálculo de Payback: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Payback Period: {type(e).__name__}"}


@tool("calcular_profitability_index", args_schema=ProfitabilityIndexInput)
def _calcular_profitability_index(tasa_descuento: float, inversion_inicial: float, flujos_caja: List[float]) -> dict:
    """Calcula el Índice de Rentabilidad (Profitability Index)."""
    logger.info(f"🔧 Calculando Profitability Index")

    try:
        tasa = tasa_descuento / 100

        # Calcular PV de flujos futuros
        pv_flujos = sum(fc / (1 + tasa)**(i+1) for i, fc in enumerate(flujos_caja))

        # PI = PV(flujos futuros) / Inversión Inicial
        pi = pv_flujos / inversion_inicial

        logger.info(f"✅ Profitability Index calculado: {pi:.4f}")
        return {
            "profitability_index": round(pi, 4),
            "interpretacion": f"PI = {pi:.4f}. Si PI > 1, el proyecto crea valor. Si PI < 1, destruye valor."
        }

    except ZeroDivisionError:
        logger.error("❌ División por cero en PI")
        return {"error": "La inversión inicial no puede ser cero."}
    except Exception as e:
        logger.error(f"❌ Error en cálculo de PI: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Profitability Index: {type(e).__name__}"}


# --- RENTA FIJA ---

@tool("calcular_duration_macaulay", args_schema=DurationMacaulayInput)
def _calcular_duration_macaulay(
    valor_nominal: float,
    tasa_cupon_anual: float,
    ytm_anual: float,
    num_anos: int,
    frecuencia_cupon: int
) -> dict:
    """Calcula la Duration Macaulay de un bono en años."""
    logger.info(f"🔧 Calculando Duration Macaulay")

    try:
        tasa_cupon_periodo = (tasa_cupon_anual / 100) / frecuencia_cupon
        ytm_periodo = (ytm_anual / 100) / frecuencia_cupon
        num_periodos = num_anos * frecuencia_cupon
        pago_cupon = valor_nominal * tasa_cupon_periodo

        # Calcular weighted cash flows
        pv_weighted_sum = 0
        pv_total = 0

        for t in range(1, num_periodos + 1):
            # Flujo en periodo t
            if t == num_periodos:
                flujo = pago_cupon + valor_nominal
            else:
                flujo = pago_cupon

            # PV del flujo
            pv_flujo = flujo / (1 + ytm_periodo)**t

            # Weighted PV (tiempo en periodos * PV)
            pv_weighted_sum += t * pv_flujo
            pv_total += pv_flujo

        # Duration Macaulay en periodos
        duration_periodos = pv_weighted_sum / pv_total if pv_total > 0 else 0

        # Convertir a años
        duration_anos = duration_periodos / frecuencia_cupon

        logger.info(f"✅ Duration Macaulay calculada: {duration_anos:.4f} años")
        return {
            "duration_macaulay_anos": round(duration_anos, 4),
            "interpretacion": f"La Duration Macaulay es {duration_anos:.2f} años (tiempo promedio ponderado de los flujos)."
        }

    except Exception as e:
        logger.error(f"❌ Error en cálculo de Duration Macaulay: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Duration Macaulay: {type(e).__name__}"}


@tool("calcular_duration_modificada", args_schema=DurationModificadaInput)
def _calcular_duration_modificada(duration_macaulay: float, ytm_anual: float, frecuencia_cupon: int) -> dict:
    """Calcula la Duration Modificada (sensibilidad del precio del bono)."""
    logger.info(f"🔧 Calculando Duration Modificada")

    try:
        ytm_periodo = (ytm_anual / 100) / frecuencia_cupon

        # Modified Duration = Macaulay Duration / (1 + YTM_per_period)
        duration_modificada = duration_macaulay / (1 + ytm_periodo)

        logger.info(f"✅ Duration Modificada calculada: {duration_modificada:.4f}")
        return {
            "duration_modificada": round(duration_modificada, 4),
            "interpretacion": f"Por cada 1% de cambio en YTM, el precio del bono cambia aproximadamente {duration_modificada:.2f}%."
        }

    except Exception as e:
        logger.error(f"❌ Error en cálculo de Duration Modificada: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Duration Modificada: {type(e).__name__}"}


@tool("calcular_convexity", args_schema=ConvexityInput)
def _calcular_convexity(
    valor_nominal: float,
    tasa_cupon_anual: float,
    ytm_anual: float,
    num_anos: int,
    frecuencia_cupon: int
) -> dict:
    """Calcula la Convexity de un bono."""
    logger.info(f"🔧 Calculando Convexity")

    try:
        tasa_cupon_periodo = (tasa_cupon_anual / 100) / frecuencia_cupon
        ytm_periodo = (ytm_anual / 100) / frecuencia_cupon
        num_periodos = num_anos * frecuencia_cupon
        pago_cupon = valor_nominal * tasa_cupon_periodo

        # Calcular convexity
        convexity_sum = 0
        pv_total = 0

        for t in range(1, num_periodos + 1):
            if t == num_periodos:
                flujo = pago_cupon + valor_nominal
            else:
                flujo = pago_cupon

            pv_flujo = flujo / (1 + ytm_periodo)**t

            # Convexity term: t*(t+1)*PV(flujo)
            convexity_sum += t * (t + 1) * pv_flujo
            pv_total += pv_flujo

        # Convexity = convexity_sum / (PV_total * (1 + y)^2 * frecuencia^2)
        convexity = convexity_sum / (pv_total * (1 + ytm_periodo)**2 * frecuencia_cupon**2)

        logger.info(f"✅ Convexity calculada: {convexity:.4f}")
        return {
            "convexity": round(convexity, 4),
            "interpretacion": f"Convexity = {convexity:.4f}. Mide la curvatura de la relación precio-yield."
        }

    except Exception as e:
        logger.error(f"❌ Error en cálculo de Convexity: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Convexity: {type(e).__name__}"}


@tool("calcular_current_yield", args_schema=CurrentYieldInput)
def _calcular_current_yield(pago_cupon_anual: float, precio_actual_bono: float) -> dict:
    """Calcula el Current Yield de un bono."""
    logger.info(f"🔧 Calculando Current Yield")

    try:
        current_yield = (pago_cupon_anual / precio_actual_bono) * 100

        logger.info(f"✅ Current Yield calculado: {current_yield:.4f}%")
        return {
            "current_yield_porcentaje": round(current_yield, 4),
            "interpretacion": f"El Current Yield es {current_yield:.2f}% (retorno anual del cupón sobre el precio actual)."
        }

    except ZeroDivisionError:
        logger.error("❌ División por cero en Current Yield")
        return {"error": "El precio actual del bono no puede ser cero."}
    except Exception as e:
        logger.error(f"❌ Error en cálculo de Current Yield: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Current Yield: {type(e).__name__}"}


@tool("calcular_bono_cupon_cero", args_schema=BonoCuponCeroInput)
def _calcular_bono_cupon_cero(valor_nominal: float, ytm_anual: float, num_anos: float) -> dict:
    """Calcula el valor presente de un Bono Cupón Cero (Zero-Coupon Bond)."""
    logger.info(f"🔧 Calculando Bono Cupón Cero: nominal={valor_nominal}, años={num_anos}")

    try:
        ytm = ytm_anual / 100

        # PV = FV / (1 + r)^T
        pv = valor_nominal / (1 + ytm)**num_anos

        logger.info(f"✅ Valor bono cupón cero: ${pv:.2f}")
        return {
            "valor_presente": round(pv, 2),
            "interpretacion": f"El valor presente del bono cupón cero es ${pv:,.2f}."
        }

    except Exception as e:
        logger.error(f"❌ Error en cálculo de bono cupón cero: {type(e).__name__} - {e}")
        return {"error": f"Error calculando bono cupón cero: {type(e).__name__}"}


# --- DERIVADOS ---

@tool("calcular_opcion_put", args_schema=OpcionPutInput)
def _calcular_opcion_put(S: float, K: float, T: float, r: float, sigma: float) -> dict:
    """Calcula el valor de una Opción Put Europea usando Black-Scholes."""
    logger.info(f"🔧 Calculando opción put: S={S}, K={K}, T={T}")

    try:
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            logger.error("❌ Parámetros inválidos en opción put")
            return {"error": "Tiempo (T), volatilidad (sigma), precio actual (S) y strike (K) deben ser positivos."}

        r_dec = r / 100
        sigma_dec = sigma / 100

        if sigma_dec == 0:
            put_price = max(K * np.exp(-r_dec * T) - S, 0)
            logger.info(f"✅ Opción put (σ=0): ${put_price:.4f}")
            return {"valor_opcion_put": round(put_price, 4)}

        denominator = sigma_dec * np.sqrt(T)
        d1 = (np.log(S / K) + (r_dec + 0.5 * sigma_dec**2) * T) / denominator
        d2 = d1 - denominator

        # Put = K*e^(-rT)*N(-d2) - S*N(-d1)
        put_price = (K * np.exp(-r_dec * T) * norm.cdf(-d2) - S * norm.cdf(-d1))
        put_price = max(put_price, 0)

        logger.info(f"✅ Opción put calculada: ${put_price:.4f}")
        return {"valor_opcion_put": round(put_price, 4)}

    except OverflowError:
        logger.error("❌ Overflow en cálculo de opción put")
        return {"error": "Error de cálculo: Overflow. Verifica inputs muy grandes/pequeños."}
    except Exception as e:
        logger.error(f"❌ Error en cálculo de opción put: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Opción Put: {type(e).__name__}"}


@tool("calcular_put_call_parity", args_schema=PutCallParityInput)
def _calcular_put_call_parity(
    precio_call: float,
    precio_put: float,
    precio_spot: float,
    strike: float,
    tiempo_vencimiento: float,
    tasa_libre_riesgo: float
) -> dict:
    """Verifica la Put-Call Parity: C + PV(K) = P + S."""
    logger.info(f"🔧 Verificando Put-Call Parity")

    try:
        r = tasa_libre_riesgo / 100

        # PV del strike
        pv_strike = strike * np.exp(-r * tiempo_vencimiento)

        # Lado izquierdo: C + PV(K)
        lado_izq = precio_call + pv_strike

        # Lado derecho: P + S
        lado_der = precio_put + precio_spot

        diferencia = abs(lado_izq - lado_der)

        es_valida = diferencia < 0.01  # Tolerancia de 1 centavo

        logger.info(f"✅ Put-Call Parity verificada: válida={es_valida}")
        return {
            "call_mas_pv_strike": round(lado_izq, 4),
            "put_mas_spot": round(lado_der, 4),
            "diferencia": round(diferencia, 4),
            "parity_valida": es_valida,
            "interpretacion": "Paridad válida (diferencia < 0.01)" if es_valida else f"Paridad NO válida (diferencia = {diferencia:.4f})"
        }

    except Exception as e:
        logger.error(f"❌ Error en Put-Call Parity: {type(e).__name__} - {e}")
        return {"error": f"Error verificando Put-Call Parity: {type(e).__name__}"}


# --- PORTAFOLIO ---

@tool("calcular_treynor_ratio", args_schema=TreynorRatioInput)
def _calcular_treynor_ratio(retorno_portafolio: float, tasa_libre_riesgo: float, beta_portafolio: float) -> dict:
    """Calcula el Treynor Ratio (retorno ajustado por riesgo sistemático)."""
    logger.info(f"🔧 Calculando Treynor Ratio")

    try:
        r_p = retorno_portafolio / 100
        r_f = tasa_libre_riesgo / 100

        if beta_portafolio <= 0:
            logger.error("❌ Beta inválido")
            return {"error": "El beta del portafolio debe ser positivo."}

        treynor = (r_p - r_f) / beta_portafolio

        logger.info(f"✅ Treynor Ratio calculado: {treynor:.4f}")
        return {
            "treynor_ratio": round(treynor, 4),
            "interpretacion": f"Treynor Ratio = {treynor:.4f}. Mayor valor indica mejor retorno ajustado por riesgo sistemático."
        }

    except Exception as e:
        logger.error(f"❌ Error en cálculo de Treynor: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Treynor Ratio: {type(e).__name__}"}


@tool("calcular_jensen_alpha", args_schema=JensenAlphaInput)
def _calcular_jensen_alpha(
    retorno_portafolio: float,
    tasa_libre_riesgo: float,
    beta_portafolio: float,
    retorno_mercado: float
) -> dict:
    """Calcula Jensen's Alpha (exceso de retorno vs CAPM)."""
    logger.info(f"🔧 Calculando Jensen's Alpha")

    try:
        r_p = retorno_portafolio / 100
        r_f = tasa_libre_riesgo / 100
        r_m = retorno_mercado / 100

        # Retorno esperado según CAPM
        retorno_esperado_capm = r_f + beta_portafolio * (r_m - r_f)

        # Alpha = Retorno real - Retorno esperado (CAPM)
        alpha = r_p - retorno_esperado_capm
        alpha_porcentaje = alpha * 100

        logger.info(f"✅ Jensen's Alpha calculado: {alpha_porcentaje:.4f}%")
        return {
            "jensen_alpha_porcentaje": round(alpha_porcentaje, 4),
            "interpretacion": f"Jensen's Alpha = {alpha_porcentaje:.2f}%. Alpha > 0 indica desempeño superior al mercado."
        }

    except Exception as e:
        logger.error(f"❌ Error en cálculo de Jensen's Alpha: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Jensen's Alpha: {type(e).__name__}"}


@tool("calcular_beta_portafolio", args_schema=BetaPortafolioInput)
def _calcular_beta_portafolio(
    peso_activo_1: float,
    peso_activo_2: float,
    beta_activo_1: float,
    beta_activo_2: float
) -> dict:
    """Calcula el Beta de un portafolio de 2 activos."""
    logger.info(f"🔧 Calculando Beta de Portafolio")

    try:
        # Validar que los pesos sumen 1
        suma_pesos = peso_activo_1 + peso_activo_2
        if not (0.99 <= suma_pesos <= 1.01):
            logger.warning(f"⚠️ Pesos no suman 1 (suma={suma_pesos})")
            return {"error": f"Los pesos deben sumar 1.0 (suma actual: {suma_pesos:.4f})"}

        # Beta portafolio = w1*β1 + w2*β2
        beta_portfolio = peso_activo_1 * beta_activo_1 + peso_activo_2 * beta_activo_2

        logger.info(f"✅ Beta portafolio calculado: {beta_portfolio:.4f}")
        return {
            "beta_portafolio": round(beta_portfolio, 4),
            "interpretacion": f"El beta del portafolio es {beta_portfolio:.4f} (riesgo sistemático)."
        }

    except Exception as e:
        logger.error(f"❌ Error en cálculo de Beta portafolio: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Beta de Portafolio: {type(e).__name__}"}


@tool("calcular_retorno_portafolio", args_schema=RetornoPortafolioInput)
def _calcular_retorno_portafolio(
    peso_activo_1: float,
    peso_activo_2: float,
    retorno_activo_1: float,
    retorno_activo_2: float
) -> dict:
    """Calcula el Retorno Esperado de un portafolio de 2 activos."""
    logger.info(f"🔧 Calculando Retorno de Portafolio")

    try:
        suma_pesos = peso_activo_1 + peso_activo_2
        if not (0.99 <= suma_pesos <= 1.01):
            logger.warning(f"⚠️ Pesos no suman 1 (suma={suma_pesos})")
            return {"error": f"Los pesos deben sumar 1.0 (suma actual: {suma_pesos:.4f})"}

        # E(Rp) = w1*R1 + w2*R2
        retorno_portfolio = peso_activo_1 * retorno_activo_1 + peso_activo_2 * retorno_activo_2

        logger.info(f"✅ Retorno portafolio calculado: {retorno_portfolio:.4f}%")
        return {
            "retorno_esperado_porcentaje": round(retorno_portfolio, 4),
            "interpretacion": f"El retorno esperado del portafolio es {retorno_portfolio:.2f}%."
        }

    except Exception as e:
        logger.error(f"❌ Error en cálculo de Retorno portafolio: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Retorno de Portafolio: {type(e).__name__}"}


@tool("calcular_std_dev_portafolio", args_schema=StdDevPortafolioInput)
def _calcular_std_dev_portafolio(
    peso_activo_1: float,
    peso_activo_2: float,
    std_dev_activo_1: float,
    std_dev_activo_2: float,
    correlacion: float
) -> dict:
    """Calcula la Desviación Estándar de un portafolio de 2 activos."""
    logger.info(f"🔧 Calculando Desviación Estándar de Portafolio")

    try:
        suma_pesos = peso_activo_1 + peso_activo_2
        if not (0.99 <= suma_pesos <= 1.01):
            logger.warning(f"⚠️ Pesos no suman 1 (suma={suma_pesos})")
            return {"error": f"Los pesos deben sumar 1.0 (suma actual: {suma_pesos:.4f})"}

        # Convertir % a decimal
        sigma1 = std_dev_activo_1 / 100
        sigma2 = std_dev_activo_2 / 100

        # σp = sqrt(w1²σ1² + w2²σ2² + 2*w1*w2*ρ*σ1*σ2)
        varianza_portfolio = (
            peso_activo_1**2 * sigma1**2 +
            peso_activo_2**2 * sigma2**2 +
            2 * peso_activo_1 * peso_activo_2 * correlacion * sigma1 * sigma2
        )

        std_dev_portfolio = np.sqrt(varianza_portfolio) * 100  # Convertir a %

        logger.info(f"✅ Desviación estándar portafolio: {std_dev_portfolio:.4f}%")
        return {
            "std_dev_portafolio_porcentaje": round(std_dev_portfolio, 4),
            "interpretacion": f"La desviación estándar del portafolio es {std_dev_portfolio:.2f}% (riesgo total)."
        }

    except Exception as e:
        logger.error(f"❌ Error en cálculo de Std Dev portafolio: {type(e).__name__} - {e}")
        return {"error": f"Error calculando Desviación Estándar de Portafolio: {type(e).__name__}"}


# ========================================
# LISTA EXPORTABLE
# ========================================

financial_tool_list = [
    # Herramientas originales (7)
    _calcular_valor_presente_bono,
    _calcular_van,
    _calcular_opcion_call,
    _calcular_wacc,
    _calcular_capm,
    _calcular_sharpe_ratio,
    _calcular_gordon_growth,
    # Nuevas herramientas CFA Level I (15)
    # Finanzas Corporativas (3)
    _calcular_tir,
    _calcular_payback_period,
    _calcular_profitability_index,
    # Renta Fija (5)
    _calcular_duration_macaulay,
    _calcular_duration_modificada,
    _calcular_convexity,
    _calcular_current_yield,
    _calcular_bono_cupon_cero,
    # Derivados (2)
    _calcular_opcion_put,
    _calcular_put_call_parity,
    # Portafolio (5)
    _calcular_treynor_ratio,
    _calcular_jensen_alpha,
    _calcular_beta_portafolio,
    _calcular_retorno_portafolio,
    _calcular_std_dev_portafolio,
]

logger.info(f"✅ Módulo financial_tools cargado ({len(financial_tool_list)} herramientas)")