export enum BrokerStatus {
    NO_SECRETS = "NO_SECRETS",
    SECRETS_SAVED = "SECRETS_SAVED",
    TOKEN_VALID = "TOKEN_VALID",
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
}

export enum MarketStatus {
    OPEN = "OPEN",
    CLOSED = "CLOSED",
    PAUSED = "PAUSED"
}

export interface OptionData {
    instrumentKey: string;
    strike: number;
    ltp: number;
    change?: number;
    changePercent?: number;
    volume: number;
    oi: number;
    iv?: number;
    delta?: number;
    theta?: number;
    gamma?: number;
    vega?: number;
    // ✅ FIX #6: Fields from REST API response (normalized to above)
    bid?: number;
    ask?: number;
    bid_quantity?: number;
    ask_quantity?: number;
    // For backward compatibility
    close?: number;
    symbol?: string;
    instrumentName?: string;
    lotSize?: number; // ✅ ADDED
}

export interface OptionChainRow {
    strike: number;
    isATM: boolean;
    isSkeleton?: boolean;
    call: OptionData;
    put: OptionData;
}
