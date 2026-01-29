import { useMarketStore } from "@/stores/marketStore";
import { Badge } from "@/components/ui/badge";
import { Activity, XCircle, Clock, AlertTriangle, Moon } from "lucide-react";

export function MarketFeedStatus() {
    const feedStatus = useMarketStore((state) => state.feedStatus);

    const statusConfig = {
        connected: {
            icon: Activity,
            label: "Live Feed",
            variant: "default" as const,
            className: "bg-green-500 hover:bg-green-600 text-white",
        },
        connecting: {
            icon: Clock,
            label: "Connecting...",
            variant: "secondary" as const,
            className: "bg-yellow-500 hover:bg-yellow-600 text-white animate-pulse",
        },
        disconnected: {
            icon: XCircle,
            label: "Disconnected",
            variant: "destructive" as const,
            className: "bg-red-500 hover:bg-red-600 text-white",
        },
        market_closed: {
            icon: Moon,
            label: "Market Closed",
            variant: "outline" as const,
            className: "bg-blue-500 hover:bg-blue-600 text-white",
        },
        unavailable: {
            icon: AlertTriangle,
            label: "Feed Unavailable",
            variant: "destructive" as const,
            className: "bg-orange-500 hover:bg-orange-600 text-white",
        },
    };

    const config = statusConfig[feedStatus] || statusConfig.disconnected;
    const Icon = config.icon;

    return (
        <Badge variant={config.variant} className={`flex items-center gap-1.5 px-3 py-1 ${config.className}`}>
            <Icon className="h-3.5 w-3.5" />
            <span className="text-xs font-medium">{config.label}</span>
        </Badge>
    );
}
