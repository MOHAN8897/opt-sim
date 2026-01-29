import React from "react";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Calendar, ChevronLeft, ChevronRight } from "lucide-react";
import { MainLayout } from "@/components/layout/MainLayout";
import { useTradeStore, Trade } from "@/stores/tradeStore";
import { useMarketStore } from "@/stores/marketStore";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const PortfolioPage: React.FC = () => {
  const { openTrades, tradeHistory } = useTradeStore();
  const { netPnl, ltpMap } = useMarketStore();
  const [page, setPage] = React.useState(1);
  const itemsPerPage = 10;

  const totalTrades = tradeHistory.length;
  const wins = tradeHistory.filter((t) => (t.pnl || 0) > 0).length;
  const losses = tradeHistory.filter((t) => (t.pnl || 0) < 0).length;
  const totalRealizedPnl = tradeHistory.reduce((acc, t) => acc + (t.pnl || 0), 0);

  const paginatedHistory = tradeHistory.slice((page - 1) * itemsPerPage, page * itemsPerPage);
  const totalPages = Math.ceil(tradeHistory.length / itemsPerPage);

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="text-2xl font-bold text-foreground">Portfolio</h1>
          <p className="mt-1 text-muted-foreground">
            Your positions and trade history
          </p>
        </motion.div>

        {/* Summary Cards */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="trade-card p-4"
          >
            <p className="text-sm text-muted-foreground">Unrealized P&L</p>
            <p className={cn("mt-1 text-2xl font-bold", netPnl >= 0 ? "pnl-profit" : "pnl-loss")}>
              {netPnl >= 0 ? "+" : ""}₹{netPnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="trade-card p-4"
          >
            <p className="text-sm text-muted-foreground">Realized P&L</p>
            <p
              className={cn(
                "mt-1 text-2xl font-bold",
                totalRealizedPnl >= 0 ? "pnl-profit" : "pnl-loss"
              )}
            >
              {totalRealizedPnl >= 0 ? "+" : ""}₹
              {totalRealizedPnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="trade-card p-4"
          >
            <p className="text-sm text-muted-foreground">Total Trades</p>
            <p className="mt-1 text-2xl font-bold text-foreground">{totalTrades}</p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="trade-card p-4"
          >
            <p className="text-sm text-muted-foreground">Win/Loss</p>
            <p className="mt-1 text-2xl font-bold">
              <span className="text-profit">{wins}</span>
              <span className="text-muted-foreground"> / </span>
              <span className="text-loss">{losses}</span>
            </p>
          </motion.div>
        </div>

        {/* Open Positions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="trade-card overflow-hidden"
        >
          <div className="border-b border-border p-4">
            <h2 className="text-lg font-semibold text-foreground">Open Positions</h2>
          </div>
          {openTrades.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <TrendingUp className="mb-3 h-10 w-10 text-muted-foreground" />
              <p className="text-muted-foreground">No open positions</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Instrument</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="text-right">Avg. Price</TableHead>
                  <TableHead className="text-right">LTP</TableHead>
                  <TableHead className="text-right">Invested</TableHead>
                  <TableHead className="text-right">P&L</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {openTrades.map((trade) => {
                  const currentLtp = ltpMap[trade.instrumentKey] || trade.entryPrice;

                  // P&L Logic:
                  // Long: (LTP - Entry) * Qty
                  // Short: (Entry - LTP) * Qty
                  let unrealizedPnl = 0;
                  if (trade.side === "BUY") {
                    unrealizedPnl = (currentLtp - trade.entryPrice) * trade.quantity;
                  } else {
                    unrealizedPnl = (trade.entryPrice - currentLtp) * trade.quantity;
                  }

                  const invested = trade.entryPrice * trade.quantity;

                  return (
                    <TableRow key={trade.id}>
                      <TableCell className="font-medium">{trade.instrumentName}</TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            "rounded px-2 py-0.5 text-xs font-semibold",
                            trade.side === "BUY" ? "bg-profit/20 text-profit" : "bg-loss/20 text-loss"
                          )}
                        >
                          {trade.side} {trade.optionType}
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-mono">{trade.quantity}</TableCell>
                      <TableCell className="text-right font-mono">
                        ₹{trade.entryPrice.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono live-pulse">
                        ₹{currentLtp.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        ₹{invested.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                      </TableCell>
                      <TableCell
                        className={cn(
                          "text-right font-mono font-semibold",
                          unrealizedPnl >= 0 ? "text-profit" : "text-loss"
                        )}
                      >
                        {unrealizedPnl >= 0 ? "+" : ""}₹{unrealizedPnl.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="destructive"
                          size="sm"
                          className="h-7 px-3 text-xs"
                          onClick={() => {
                            // Close Trade Action
                            // Import closeTrade from store inside the component if needed, 
                            // but we are inside the map.
                            // We need to use the store function.
                            useTradeStore.getState().closeTrade(trade.id, currentLtp);
                          }}
                        >
                          Close
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </motion.div>

        {/* Trade History */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="trade-card overflow-hidden"
        >
          <div className="border-b border-border p-4">
            <h2 className="text-lg font-semibold text-foreground">Trade History</h2>
          </div>
          {tradeHistory.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Calendar className="mb-3 h-10 w-10 text-muted-foreground" />
              <p className="text-muted-foreground">No trade history yet</p>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Instrument</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="text-right">Entry</TableHead>
                    <TableHead className="text-right">Exit</TableHead>
                    <TableHead className="text-right">P&L</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedHistory.map((trade) => (
                    <TableRow key={trade.id}>
                      <TableCell className="text-muted-foreground">
                        {new Date(trade.closedAt || "").toLocaleDateString("en-IN")}
                      </TableCell>
                      <TableCell className="font-medium">{trade.instrumentName}</TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            "rounded px-2 py-0.5 text-xs font-semibold",
                            trade.side === "BUY" ? "bg-profit/20 text-profit" : "bg-loss/20 text-loss"
                          )}
                        >
                          {trade.side} {trade.optionType}
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        ₹{trade.entryPrice.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        ₹{trade.exitPrice?.toFixed(2)}
                      </TableCell>
                      <TableCell
                        className={cn(
                          "text-right font-mono font-semibold",
                          (trade.pnl || 0) >= 0 ? "text-profit" : "text-loss"
                        )}
                      >
                        {(trade.pnl || 0) >= 0 ? "+" : ""}₹{trade.pnl?.toFixed(2)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between border-t border-border p-4">
                  <p className="text-sm text-muted-foreground">
                    Page {page} of {totalPages}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </motion.div>
      </div>
    </MainLayout>
  );
};

export default PortfolioPage;
