"""
Tests unitarios para herramientas financieras.
Valida que los cálculos sean correctos y el manejo de errores sea robusto.
"""

import pytest
from tools.financial_tools import (
    _calcular_van, _calcular_wacc, _calcular_capm,
    _calcular_valor_presente_bono, _calcular_opcion_call,
    _calcular_sharpe_ratio, _calcular_gordon_growth,
    _calcular_tir, _calcular_payback_period
)


# ========================================
# TESTS VAN (NPV)
# ========================================

def test_van_proyecto_rentable():
    """Test VAN positivo - proyecto rentable"""
    result = _calcular_van.invoke({
        "tasa_descuento": 10.0,
        "inversion_inicial": 100000.0,
        "flujos_caja": [30000, 40000, 50000]
    })

    assert "van" in result
    assert result["van"] > 0  # Debe ser rentable
    assert abs(result["van"] - 2892.37) < 1  # Valor esperado ~$2,892


def test_van_proyecto_no_rentable():
    """Test VAN negativo - proyecto no rentable"""
    result = _calcular_van.invoke({
        "tasa_descuento": 25.0,  # Alta tasa de descuento
        "inversion_inicial": 100000.0,
        "flujos_caja": [20000, 25000, 30000]
    })

    assert "van" in result
    assert result["van"] < 0  # No rentable


def test_van_flujos_vacios():
    """Test VAN con lista de flujos vacía"""
    result = _calcular_van.invoke({
        "tasa_descuento": 10.0,
        "inversion_inicial": 100000.0,
        "flujos_caja": []
    })

    assert "van" in result
    assert result["van"] == -100000.0  # Solo la inversión


# ========================================
# TESTS WACC
# ========================================

def test_wacc_calculo_correcto():
    """Test WACC con valores típicos"""
    result = _calcular_wacc.invoke({
        "tasa_impuestos": 30.0,
        "costo_deuda": 8.0,
        "costo_equity": 12.0,
        "valor_mercado_deuda": 400000.0,
        "valor_mercado_equity": 600000.0
    })

    assert "wacc_porcentaje" in result
    # WACC = 0.6*12% + 0.4*8%*(1-0.3) = 7.2% + 2.24% = 9.44%
    assert abs(result["wacc_porcentaje"] - 9.44) < 0.1


def test_wacc_sin_deuda():
    """Test WACC cuando no hay deuda"""
    result = _calcular_wacc.invoke({
        "tasa_impuestos": 30.0,
        "costo_deuda": 0.0,
        "costo_equity": 15.0,
        "valor_mercado_deuda": 0.0,
        "valor_mercado_equity": 1000000.0
    })

    assert "wacc_porcentaje" in result
    assert result["wacc_porcentaje"] == 15.0  # Solo equity


def test_wacc_valores_negativos():
    """Test WACC con valores negativos - debe retornar error"""
    result = _calcular_wacc.invoke({
        "tasa_impuestos": 30.0,
        "costo_deuda": 8.0,
        "costo_equity": 12.0,
        "valor_mercado_deuda": -100000.0,  # Negativo
        "valor_mercado_equity": 600000.0
    })

    assert "error" in result


# ========================================
# TESTS CAPM
# ========================================

def test_capm_calculo_correcto():
    """Test CAPM con valores típicos"""
    result = _calcular_capm.invoke({
        "tasa_libre_riesgo": 5.0,
        "beta": 1.2,
        "retorno_mercado": 12.0
    })

    assert "costo_equity_porcentaje" in result
    # Ke = 5% + 1.2 * (12% - 5%) = 5% + 8.4% = 13.4%
    assert abs(result["costo_equity_porcentaje"] - 13.4) < 0.01


def test_capm_beta_cero():
    """Test CAPM con beta = 0 (activo sin riesgo)"""
    result = _calcular_capm.invoke({
        "tasa_libre_riesgo": 5.0,
        "beta": 0.0,
        "retorno_mercado": 12.0
    })

    assert "costo_equity_porcentaje" in result
    assert result["costo_equity_porcentaje"] == 5.0  # Igual a tasa libre riesgo


def test_capm_beta_negativo():
    """Test CAPM con beta negativo (activo defensivo extremo)"""
    result = _calcular_capm.invoke({
        "tasa_libre_riesgo": 5.0,
        "beta": -0.5,
        "retorno_mercado": 12.0
    })

    assert "costo_equity_porcentaje" in result
    # Ke = 5% + (-0.5) * (12% - 5%) = 5% - 3.5% = 1.5%
    assert abs(result["costo_equity_porcentaje"] - 1.5) < 0.01


# ========================================
# TESTS BONO
# ========================================

def test_bono_par():
    """Test bono cotizando a la par (cupón = YTM)"""
    result = _calcular_valor_presente_bono.invoke({
        "valor_nominal": 1000.0,
        "tasa_cupon_anual": 6.0,
        "tasa_descuento_anual": 6.0,
        "num_anos": 10,
        "frecuencia_cupon": 2
    })

    assert "valor_presente_bono" in result
    assert abs(result["valor_presente_bono"] - 1000.0) < 1  # Debe cotizar a la par


def test_bono_descuento():
    """Test bono cotizando con descuento (YTM > cupón)"""
    result = _calcular_valor_presente_bono.invoke({
        "valor_nominal": 1000.0,
        "tasa_cupon_anual": 5.0,
        "tasa_descuento_anual": 7.0,  # YTM mayor
        "num_anos": 10,
        "frecuencia_cupon": 2
    })

    assert "valor_presente_bono" in result
    assert result["valor_presente_bono"] < 1000.0  # Descuento


def test_bono_premium():
    """Test bono cotizando con prima (cupón > YTM)"""
    result = _calcular_valor_presente_bono.invoke({
        "valor_nominal": 1000.0,
        "tasa_cupon_anual": 7.0,  # Cupón mayor
        "tasa_descuento_anual": 5.0,
        "num_anos": 10,
        "frecuencia_cupon": 2
    })

    assert "valor_presente_bono" in result
    assert result["valor_presente_bono"] > 1000.0  # Prima


# ========================================
# TESTS OPCIÓN CALL (BLACK-SCHOLES)
# ========================================

def test_opcion_call_in_the_money():
    """Test opción call in-the-money"""
    result = _calcular_opcion_call.invoke({
        "S": 110.0,  # Spot > Strike
        "K": 100.0,
        "T": 1.0,
        "r": 5.0,
        "sigma": 20.0
    })

    assert "valor_opcion_call" in result
    assert result["valor_opcion_call"] > 10.0  # Valor intrínseco mínimo


def test_opcion_call_at_the_money():
    """Test opción call at-the-money"""
    result = _calcular_opcion_call.invoke({
        "S": 100.0,
        "K": 100.0,
        "T": 1.0,
        "r": 5.0,
        "sigma": 20.0
    })

    assert "valor_opcion_call" in result
    assert result["valor_opcion_call"] > 0  # Tiene valor temporal


def test_opcion_call_parametros_negativos():
    """Test opción call con parámetros inválidos"""
    result = _calcular_opcion_call.invoke({
        "S": -100.0,  # Negativo
        "K": 100.0,
        "T": 1.0,
        "r": 5.0,
        "sigma": 20.0
    })

    assert "error" in result


# ========================================
# TESTS SHARPE RATIO
# ========================================

def test_sharpe_ratio_positivo():
    """Test Sharpe ratio con exceso de retorno positivo"""
    result = _calcular_sharpe_ratio.invoke({
        "retorno_portafolio": 15.0,
        "tasa_libre_riesgo": 5.0,
        "std_dev_portafolio": 20.0
    })

    assert "sharpe_ratio" in result
    # Sharpe = (15% - 5%) / 20% = 0.5
    assert abs(result["sharpe_ratio"] - 0.5) < 0.01


def test_sharpe_ratio_negativo():
    """Test Sharpe ratio con retorno menor a rf"""
    result = _calcular_sharpe_ratio.invoke({
        "retorno_portafolio": 3.0,  # Menor que rf
        "tasa_libre_riesgo": 5.0,
        "std_dev_portafolio": 20.0
    })

    assert "sharpe_ratio" in result
    assert result["sharpe_ratio"] < 0


# ========================================
# TESTS GORDON GROWTH
# ========================================

def test_gordon_growth_valido():
    """Test Gordon Growth con parámetros válidos"""
    result = _calcular_gordon_growth.invoke({
        "dividendo_prox_periodo": 2.5,
        "tasa_descuento_equity": 10.0,
        "tasa_crecimiento_dividendos": 3.0
    })

    assert "valor_accion" in result
    # P0 = D1 / (Ke - g) = 2.5 / (0.10 - 0.03) = 2.5 / 0.07 = 35.71
    assert abs(result["valor_accion"] - 35.71) < 0.1


def test_gordon_growth_ke_menor_que_g():
    """Test Gordon Growth con g >= Ke (inválido)"""
    result = _calcular_gordon_growth.invoke({
        "dividendo_prox_periodo": 2.5,
        "tasa_descuento_equity": 5.0,
        "tasa_crecimiento_dividendos": 7.0  # Mayor que Ke
    })

    assert "error" in result  # Debe retornar error


# ========================================
# TESTS TIR (IRR)
# ========================================

def test_tir_proyecto_rentable():
    """Test TIR mayor que tasa de descuento"""
    result = _calcular_tir.invoke({
        "inversion_inicial": 100000.0,
        "flujos_caja": [40000, 45000, 50000]
    })

    assert "tir_porcentaje" in result
    assert result["tir_porcentaje"] > 0


def test_tir_flujos_uniformes():
    """Test TIR con flujos uniformes"""
    result = _calcular_tir.invoke({
        "inversion_inicial": 100000.0,
        "flujos_caja": [30000, 30000, 30000, 30000]
    })

    assert "tir_porcentaje" in result
    # Con 4 flujos de 30k, TIR debería ser ~7.7%
    assert 7.0 < result["tir_porcentaje"] < 9.0


# ========================================
# TESTS PAYBACK PERIOD
# ========================================

def test_payback_period_exacto():
    """Test Payback cuando se recupera exactamente en un periodo"""
    result = _calcular_payback_period.invoke({
        "inversion_inicial": 100000.0,
        "flujos_caja": [40000, 60000, 30000]  # Se recupera en periodo 2
    })

    assert "payback_period_anos" in result
    assert 1.0 < result["payback_period_anos"] < 2.5


def test_payback_period_nunca_recupera():
    """Test Payback cuando nunca se recupera la inversión"""
    result = _calcular_payback_period.invoke({
        "inversion_inicial": 100000.0,
        "flujos_caja": [10000, 15000, 20000]  # Total 45k < 100k
    })

    assert "payback_period_anos" in result or "error" in result


# ========================================
# RUNNER
# ========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
