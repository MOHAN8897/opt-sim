import React, { useCallback } from "react";
import { cn } from "@/lib/utils";
import { OptionChainRow, OptionData } from "@/types/trading";
import { OptionRow } from "./OptionRow";

interface OptionChainTableProps {
    data: OptionChainRow[];
    isLoading: boolean;
    columns: any;
    currentSpotPrice: number;
    isTradeDisabled: boolean;
    useCompactButtons: boolean;
    handleBuySell: (option: OptionData, type: "CE" | "PE", action: "BUY" | "SELL") => void;
    getColSpan: () => number;
    currentATMStrike: number; // ✅ O(1) derived prop
    liveStrikes: Set<number>; // ✅ O(1) Set
}

export const OptionChainTable: React.FC<OptionChainTableProps> = ({
    data,
    isLoading,
    columns,
    currentSpotPrice,
    isTradeDisabled,
    useCompactButtons,
    handleBuySell,
    getColSpan,
    currentATMStrike,
    liveStrikes,
}) => {
    // Refactor: Use visibleColumns array for alignment
    const visibleColumns = Object.entries(columns).filter(([_, visible]) => visible).map(([key]) => key);
    const sideColSpan = visibleColumns.length + 2; // LTP, Action
    const totalColSpan = sideColSpan * 2 + 1;

    const renderSpotRow = useCallback((strike: number) => (
        <tr key={`spot-row-${strike}`} className="bg-secondary/50 border-y border-primary/20">
            <td colSpan={totalColSpan} className="py-0.5 px-2 text-center">
                <div className="flex items-center justify-center gap-3">
                    <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-widest">Spot Price</span>
                    <span className="text-xs font-bold font-mono text-primary">{currentSpotPrice.toFixed(2)}</span>
                </div>
            </td>
        </tr>
    ), [totalColSpan, currentSpotPrice]);

    return (
        <div className="flex-1 overflow-x-auto overflow-y-auto pr-1 md:pr-4">
            <table className="w-full table-auto relative border-collapse whitespace-nowrap">
                <colgroup>{columns.oi && <col className="w-[80px]" />}{columns.volume && <col className="w-[70px]" />}{columns.delta && <col className="w-[60px]" />}{columns.theta && <col className="w-[60px]" />}{columns.gamma && <col className="w-[60px]" />}{columns.vega && <col className="w-[60px]" />}{columns.iv && <col className="w-[70px]" />}{columns.change && <col className="w-[70px]" />}<col className="w-[90px]" /><col className="w-[60px]" /><col className="w-[100px]" /><col className="w-[60px]" /><col className="w-[90px]" />{columns.change && <col className="w-[70px]" />}{columns.iv && <col className="w-[70px]" />}{columns.vega && <col className="w-[60px]" />}{columns.gamma && <col className="w-[60px]" />}{columns.theta && <col className="w-[60px]" />}{columns.delta && <col className="w-[60px]" />}{columns.volume && <col className="w-[70px]" />}{columns.oi && <col className="w-[80px]" />}</colgroup>
                <thead className="sticky top-0 z-10 bg-background border-b">
                    <tr className="border-b border-border text-xs text-muted-foreground">
                        <th colSpan={sideColSpan} className="bg-[hsl(var(--call-bg))] px-2 py-1 text-center text-call font-bold tracking-wider border-r border-border/20">CALLS</th>
                        <th className="bg-secondary px-2 py-1 text-center font-bold text-foreground border-x border-border">STRIKE</th>
                        <th colSpan={sideColSpan} className="bg-[hsl(var(--put-bg))] px-2 py-1 text-center text-put font-bold tracking-wider border-l border-border/20">PUTS</th>
                    </tr>
                    <tr className="border-b border-border text-xs text-muted-foreground bg-background">
                        {columns.oi && <th className="bg-[hsl(var(--call-bg))] px-2 py-1 text-right text-xs">OI</th>}
                        {columns.volume && <th className="bg-[hsl(var(--call-bg))] px-2 py-1 text-right text-xs">Vol</th>}
                        {columns.delta && <th className="bg-[hsl(var(--call-bg))] px-2 py-1 text-right text-xs">Delta</th>}
                        {columns.theta && <th className="bg-[hsl(var(--call-bg))] px-2 py-1 text-right text-xs">Theta</th>}
                        {columns.gamma && <th className="bg-[hsl(var(--call-bg))] px-2 py-1 text-right text-xs">Gamma</th>}
                        {columns.vega && <th className="bg-[hsl(var(--call-bg))] px-2 py-1 text-right text-xs">Vega</th>}
                        {columns.iv && <th className="bg-[hsl(var(--call-bg))] px-2 py-1 text-right text-xs">IV</th>}

                        {columns.change && <th className="bg-[hsl(var(--call-bg))] px-2 py-1 text-right text-xs">Chg%</th>}
                        <th className="bg-[hsl(var(--call-bg))] px-2 py-1 text-right font-medium text-foreground text-xs">LTP</th>
                        <th className="bg-[hsl(var(--call-bg))] px-2 py-1 text-center font-xs">Act</th>

                        <th className="bg-secondary px-3 py-1 text-center min-w-[100px] border-x border-border text-xs">Strike</th>

                        <th className="bg-[hsl(var(--put-bg))] px-2 py-1 text-center font-xs">Act</th>
                        <th className="bg-[hsl(var(--put-bg))] px-2 py-1 text-right font-medium text-foreground text-xs">LTP</th>
                        {columns.change && <th className="bg-[hsl(var(--put-bg))] px-2 py-1 text-right text-xs">Chg%</th>}

                        {columns.iv && <th className="bg-[hsl(var(--put-bg))] px-2 py-1 text-left text-xs">IV</th>}
                        {columns.vega && <th className="bg-[hsl(var(--put-bg))] px-2 py-1 text-left text-xs">Vega</th>}
                        {columns.gamma && <th className="bg-[hsl(var(--put-bg))] px-2 py-1 text-left text-xs">Gamma</th>}
                        {columns.theta && <th className="bg-[hsl(var(--put-bg))] px-2 py-1 text-left text-xs">Theta</th>}
                        {columns.delta && <th className="bg-[hsl(var(--put-bg))] px-2 py-1 text-left text-xs">Delta</th>}
                        {columns.volume && <th className="bg-[hsl(var(--put-bg))] px-2 py-1 text-right text-xs">Vol</th>}
                        {columns.oi && <th className="bg-[hsl(var(--put-bg))] px-2 py-1 text-right text-xs">OI</th>}
                    </tr>
                </thead>
                <tbody>
                    {isLoading && data.length === 0 ? (
                        <tr><td colSpan={totalColSpan} className="py-20 text-center text-muted-foreground">Loading Data...</td></tr>
                    ) : (
                        data.map((row, index) => {
                            const showSpotRow = row.strike <= currentSpotPrice && (index === data.length - 1 || data[index + 1].strike > currentSpotPrice);
                            return (
                                <React.Fragment key={row.strike}>
                                    <OptionRow
                                        row={row} // Still needed for static data (Strike, Expiry)
                                        callKey={row.call.instrumentKey} // Explicit Key Passage for subscription
                                        putKey={row.put.instrumentKey}
                                        columns={columns}
                                        isTradeDisabled={isTradeDisabled}
                                        useCompactButtons={useCompactButtons}
                                        handleBuySell={handleBuySell}
                                        isATM={row.strike === currentATMStrike} // ✅ O(1) Check
                                        isLive={liveStrikes.size === 0 || liveStrikes.has(row.strike)} // ✅ O(1) Check (If set empty, treat all as live?) 
                                    // Actually if set is empty, it means we have no live subscription yet. We should probably Dim all?
                                    // Or wait. If liveStrikes is empty, `useOptionChainData` considers feed dead.
                                    // Let's stick to strict checking: liveStrikes.has(row.strike).
                                    // But on initial load liveStrikes is empty. We don't want to dim everything immediately?
                                    // Actually we DO want to dim them to indicate "Connecting...".
                                    />
                                    {showSpotRow && renderSpotRow(row.strike)}
                                </React.Fragment>
                            );
                        })
                    )}
                </tbody>
            </table>
        </div>
    );
};
