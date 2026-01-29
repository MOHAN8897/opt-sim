import React from "react";
import { Search, ChevronsUpDown, Check, SlidersHorizontal, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandItem,
    CommandList,
} from "@/components/ui/command";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";
import {
    DropdownMenu,
    DropdownMenuCheckboxItem,
    DropdownMenuContent,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { BrokerStatus, MarketStatus } from "@/types/trading";

interface OptionChainHeaderProps {
    selectedInstrument: { name: string; key: string };
    setSelectedInstrument: (inst: { name: string; key: string }) => void;
    searchQuery: string;
    setSearchQuery: (query: string) => void;
    searchResults: any[];
    isSearchOpen: boolean;
    setIsSearchOpen: (open: boolean) => void;
    expiryDates: string[];
    expiryDate: string;
    setExpiryDate: (date: string) => void;
    strikeStep?: number;
    backendATM?: number;
    columns: any;
    toggleColumn: (key: any) => void;
    isTradeDisabled: boolean;
    brokerStatus: BrokerStatus;
    marketStatus: MarketStatus | string;
}

export const OptionChainHeader: React.FC<OptionChainHeaderProps> = ({
    selectedInstrument,
    setSelectedInstrument,
    searchQuery,
    setSearchQuery,
    searchResults,
    isSearchOpen,
    setIsSearchOpen,
    expiryDates,
    expiryDate,
    setExpiryDate,
    strikeStep,
    backendATM,
    columns,
    toggleColumn,
    isTradeDisabled,
    brokerStatus,
    marketStatus,
}) => {
    return (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 md:gap-0 border-b border-border p-2 md:p-4 flex-shrink-0">
            <div className="flex flex-wrap items-center gap-2 md:gap-4 w-full sm:w-auto">
                <div className="flex items-center gap-2">
                    <Popover open={isSearchOpen} onOpenChange={setIsSearchOpen}>
                        <PopoverTrigger asChild>
                            <Button variant="outline" role="combobox" aria-expanded={isSearchOpen} className="w-[200px] md:w-[250px] justify-between">
                                {selectedInstrument.name}
                                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                            </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-[300px] p-0">
                            <Command>
                                <div className="flex items-center border-b px-3" cmdk-input-wrapper="">
                                    <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
                                    <input
                                        className="flex h-11 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
                                        placeholder="Search indices or stocks..."
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                    />
                                </div>
                                <CommandList>
                                    <CommandEmpty>No results found.</CommandEmpty>
                                    <CommandGroup heading="Suggestions">
                                        {searchResults.map((instrument: any) => (
                                            <CommandItem
                                                key={instrument.key}
                                                value={instrument.key}
                                                onSelect={() => {
                                                    setSelectedInstrument({ name: instrument.name, key: instrument.key });
                                                    setIsSearchOpen(false);
                                                }}
                                            >
                                                <Check className={cn("mr-2 h-4 w-4", selectedInstrument.key === instrument.key ? "opacity-100" : "opacity-0")} />
                                                <div className="flex flex-col">
                                                    <span>{instrument.name}</span>
                                                    <span className="text-xs text-muted-foreground">{instrument.type}</span>
                                                </div>
                                            </CommandItem>
                                        ))}
                                    </CommandGroup>
                                </CommandList>
                            </Command>
                        </PopoverContent>
                    </Popover>
                </div>

                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span>Expiry:</span>
                    {expiryDates.length > 0 ? (
                        <select
                            className="h-8 rounded-md border border-input bg-background px-2 py-1 text-xs"
                            value={expiryDate}
                            onChange={(e) => setExpiryDate(e.target.value)}
                        >
                            {expiryDates.map(date => <option key={date} value={date}>{date}</option>)}
                        </select>
                    ) : <span className="text-xs italic">Loading...</span>}
                </div>

                <div className="hidden md:flex items-center gap-4 text-xs font-medium border-l pl-4 ml-4 h-8 bg-muted/20 px-3 rounded-md">
                    <span className="text-muted-foreground">Step: <span className="text-foreground">{strikeStep || '-'}</span></span>
                    <span className="text-muted-foreground">ATM: <span className="text-foreground">{backendATM || '-'}</span></span>
                </div>
            </div>

            <div className="flex items-center gap-2 md:gap-3 ml-auto">
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="sm" className="h-8 gap-2">
                            <SlidersHorizontal className="h-3.5 w-3.5" />
                            <span>Columns</span>
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-56">
                        <DropdownMenuLabel>Visible Columns</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuCheckboxItem checked={columns.change} onCheckedChange={() => toggleColumn("change")}>Chg (Change %)</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={columns.oi} onCheckedChange={() => toggleColumn("oi")}>OI (Open Interest)</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={columns.volume} onCheckedChange={() => toggleColumn("volume")}>Volume</DropdownMenuCheckboxItem>

                        <DropdownMenuSeparator />
                        <DropdownMenuLabel>Greeks</DropdownMenuLabel>
                        <DropdownMenuCheckboxItem checked={columns.iv} onCheckedChange={() => toggleColumn("iv")}>IV (Implied Volatility)</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={columns.delta} onCheckedChange={() => toggleColumn("delta")}>Delta</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={columns.theta} onCheckedChange={() => toggleColumn("theta")}>Theta</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={columns.gamma} onCheckedChange={() => toggleColumn("gamma")}>Gamma</DropdownMenuCheckboxItem>
                        <DropdownMenuCheckboxItem checked={columns.vega} onCheckedChange={() => toggleColumn("vega")}>Vega</DropdownMenuCheckboxItem>
                    </DropdownMenuContent>
                </DropdownMenu>

                {(isTradeDisabled && marketStatus !== MarketStatus.CLOSED) && (
                    <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-1.5 text-sm text-destructive">
                        <Info className="h-4 w-4" />
                        {brokerStatus !== BrokerStatus.TOKEN_VALID ? "Broker disconnected" : "Engine paused"}
                    </div>
                )}
            </div>
        </div>
    );
};
