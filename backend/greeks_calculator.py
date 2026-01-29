import numpy as np
from scipy.stats import norm
from datetime import datetime
from typing import Dict
import logging

logger = logging.getLogger("api.greeks")

# ⚠️ NOTE: Risk Free Rate is currently static.
# For precise production use, this should be configurable or sourced dynamically.
RISK_FREE_RATE = 0.06  # 6% annual risk-free rate (India government bonds)

def calculate_greeks(
    spot_price: float,
    strike_price: float,
    time_to_expiry_days: float,
    option_ltp: float,
    option_type: str  # "CE" or "PE"
) -> Dict[str, float]:
    """
    Calculate option Greeks using Black-Scholes model.
    
    Args:
        spot_price: Current price of underlying
        strike_price: Strike price of option
        time_to_expiry_days: Days until expiry
        option_ltp: Current Last Traded Price of option
        option_type: "CE" for Call, "PE" for Put
    
    Returns:
        Dictionary with iv, delta, theta, gamma, vega
    """
    # Validate inputs
    # If expiry is today (days=0), we use a small epsilon for Time to avoid division by zero
    if spot_price <= 0 or strike_price <= 0 or option_ltp <= 0:
        return {"iv": 0, "delta": 0, "theta": 0, "gamma": 0, "vega": 0}
    
    # Handle expiry day: if days <= 0, use min time (e.g. 1 minute = 1/(365*24*60))
    # OR if strictly negative (expired yesterday), return 0s.
    if time_to_expiry_days < 0:
        return {"iv": 0, "delta": 0, "theta": 0, "gamma": 0, "vega": 0}
        
    days = max(time_to_expiry_days, 0.01) # Minimum 0.01 days (~15 mins) to prevent math errors
    
    # Convert days to years
    T = days / 365.0
    
    try:
        # Calculate Implied Volatility
        iv = calculate_implied_volatility(
            spot_price, strike_price, T, option_ltp, option_type
        )
        
        if iv == 0 or iv > 5.0:  # Cap at 500% volatility (unrealistic)
            return {"iv": 0, "delta": 0, "theta": 0, "gamma": 0, "vega": 0}
        
        # Calculate d1 and d2
        d1 = (np.log(spot_price / strike_price) + (RISK_FREE_RATE + 0.5 * iv ** 2) * T) / (iv * np.sqrt(T))
        d2 = d1 - iv * np.sqrt(T)
        
        # Calculate Greeks based on option type
        if option_type == "CE":
            delta = norm.cdf(d1)
            theta = (-(spot_price * norm.pdf(d1) * iv) / (2 * np.sqrt(T)) 
                     - RISK_FREE_RATE * strike_price * np.exp(-RISK_FREE_RATE * T) * norm.cdf(d2)) / 365
        else:  # PE
            delta = norm.cdf(d1) - 1
            theta = (-(spot_price * norm.pdf(d1) * iv) / (2 * np.sqrt(T)) 
                     + RISK_FREE_RATE * strike_price * np.exp(-RISK_FREE_RATE * T) * norm.cdf(-d2)) / 365
        
        # Gamma and Vega are same for Call and Put
        gamma = norm.pdf(d1) / (spot_price * iv * np.sqrt(T))
        vega = spot_price * norm.pdf(d1) * np.sqrt(T) / 100  # Vega per 1% change in volatility
        
        # Validate and sanitize outputs (JSON doesn't support NaN)
        def safe_val(x):
            if np.isnan(x) or np.isinf(x): return 0.0
            return round(float(x), 4)

        return {
            "iv": safe_val(iv),
            "delta": safe_val(delta),
            "theta": safe_val(theta),
            "gamma": round(safe_val(gamma), 6), # Gamma usually needs more precision
            "vega": safe_val(vega)
        }
    
    except Exception as e:
        logger.error(f"Greeks calculation error: {e}")
        return {"iv": 0, "delta": 0, "theta": 0, "gamma": 0, "vega": 0}


def calculate_implied_volatility(
    spot: float,
    strike: float,
    T: float,
    market_price: float,
    option_type: str,
    max_iterations: int = 100,
    tolerance: float = 1e-5
) -> float:
    """
    Calculate Implied Volatility using Newton-Raphson method.
    
    Args:
        spot: Spot price
        strike: Strike price
        T: Time to expiry in years
        market_price: Current market price of option
        option_type: "CE" or "PE"
        max_iterations: Maximum iterations for convergence
        tolerance: Convergence tolerance
    
    Returns:
        Implied volatility (annualized)
    """
    sigma = 0.3  # Initial guess: 30% volatility
    
    for i in range(max_iterations):
        try:
            price = black_scholes_price(spot, strike, T, sigma, option_type)
            vega = black_scholes_vega(spot, strike, T, sigma)
            
            diff = price - market_price
            
            # Check convergence
            if abs(diff) < tolerance:
                return sigma
            
            # Avoid division by zero
            if vega < 1e-10:
                break
            
            # Newton-Raphson step
            sigma = sigma - diff / vega
            
            # Keep sigma positive and reasonable
            if sigma <= 0:
                return 0
            if sigma > 5.0:  # Cap at 500%
                return 5.0
                
        except Exception as e:
            logger.debug(f"IV iteration {i} error: {e}")
            break
    
    # Return last valid sigma if converged somewhat
    return sigma if 0 < sigma < 5.0 else 0


def black_scholes_price(S: float, K: float, T: float, sigma: float, option_type: str) -> float:
    """
    Calculate Black-Scholes option price.
    
    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        sigma: Volatility
        option_type: "CE" or "PE"
    
    Returns:
        Theoretical option price
    """
    d1 = (np.log(S / K) + (RISK_FREE_RATE + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == "CE":
        return S * norm.cdf(d1) - K * np.exp(-RISK_FREE_RATE * T) * norm.cdf(d2)
    else:  # PE
        return K * np.exp(-RISK_FREE_RATE * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def black_scholes_vega(S: float, K: float, T: float, sigma: float) -> float:
    """
    Calculate Black-Scholes vega (sensitivity to volatility).
    
    Returns:
        Vega value
    """
    d1 = (np.log(S / K) + (RISK_FREE_RATE + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return S * norm.pdf(d1) * np.sqrt(T)
