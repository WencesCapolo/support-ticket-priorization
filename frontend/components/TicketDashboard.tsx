"use client";

import { useEffect, useState } from "react";
import { RotateCcw, Ghost, RefreshCw, Flame, Database } from "lucide-react";
import { Ticket, SortStrategy, Scenario } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TicketDetailModal } from "@/components/TicketDetailModal";

const API_BASE_URL = "http://localhost:8000";

export default function TicketDashboard() {
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [strategy, setStrategy] = useState<SortStrategy>("priority");
    const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [scenario, setScenario] = useState<Scenario>("default");

    const fetchTickets = async (selectedScenario: Scenario = scenario) => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}/tickets/scored?status=open&scenario=${selectedScenario}`);

            if (!response.ok) {
                throw new Error(`API Error: ${response.status}`);
            }

            const data: Ticket[] = await response.json();

            // Backend now provides real sentiment_score from TextBlob
            setTickets(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to fetch tickets");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTickets(scenario);
    }, [scenario]);

    // Sort tickets based on active strategy
    const sortedTickets = [...tickets].sort((a, b) => {
        if (strategy === "sentiment") {
            // Legacy: Sort by sentiment ascending (most negative first)
            return a.sentiment_score - b.sentiment_score;
        } else {
            // AI Risk: Sort by priority score descending (highest risk first)
            return b.priority_score - a.priority_score;
        }
    });

    const truncateSubject = (subject: string | undefined, maxLength = 60) => {
        if (!subject) return "No subject";
        return subject.length > maxLength
            ? subject.substring(0, maxLength) + "..."
            : subject;
    };

    const getSentimentColor = (score?: number): string => {
        if (score === undefined) return "bg-gray-100 text-gray-800";
        if (score > 0.2) return "bg-green-100 text-green-800";
        if (score < -0.2) return "bg-red-100 text-red-800";
        return "bg-yellow-100 text-yellow-800";
    };

    const getPriorityColor = (score: number): string => {
        if (score >= 70) return "bg-red-600 text-white";
        if (score >= 50) return "bg-orange-500 text-white";
        if (score >= 30) return "bg-yellow-500 text-white";
        return "bg-gray-400 text-white";
    };

    const getMRRBadgeColor = (mrr: number | null): string => {
        if (!mrr) return "bg-gray-200 text-gray-700";
        return mrr > 3000 ? "bg-amber-400 text-amber-950 font-semibold" : "bg-blue-100 text-blue-700";
    };

    const isHiddenFire = (ticket: Ticket): boolean => {
        // Hidden Fire: High priority score (>70), significant silence, and enterprise value
        return ticket.priority_score >= 70 && ticket.silence_days > 5;
    };

    const isHighRisk = (ticket: Ticket): boolean => {
        // High risk threshold: 50+ points
        return ticket.priority_score >= 50;
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-12">
                <div className="flex items-center gap-2">
                    <RefreshCw className="h-5 w-5 animate-spin" />
                    <span className="text-lg text-gray-600">Loading tickets...</span>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="rounded-lg border border-red-200 bg-red-50 p-6">
                <h3 className="font-semibold text-red-900">Error Loading Tickets</h3>
                <p className="text-red-700">{error}</p>
                <p className="mt-2 text-sm text-red-600">
                    Make sure the backend is running at {API_BASE_URL}
                </p>
                <Button onClick={() => fetchTickets()} className="mt-4" variant="outline">
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Retry
                </Button>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Strategy Toggle */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Ticket Prioritization</h2>
                    <p className="text-sm text-gray-500 mt-1">
                        {strategy === "sentiment"
                            ? "Sorted by sentiment (ascending) - The old way"
                            : "Sorted by AI Risk Score (descending) - The Ontop way"}
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    <Button onClick={() => fetchTickets()} variant="outline" size="sm">
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Scenario Selector */}
            <div className="flex items-center gap-4 p-4 bg-gradient-to-r from-indigo-50 to-purple-50 rounded-lg border border-indigo-100">
                <div className="flex items-center gap-2">
                    <Database className="h-5 w-5 text-indigo-600" />
                    <span className="font-medium text-gray-700">Data Source:</span>
                </div>
                <div className="flex gap-2">
                    <Button
                        variant={scenario === "default" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setScenario("default")}
                        className={scenario === "default" ? "bg-indigo-600 hover:bg-indigo-700" : ""}
                    >
                        📊 Provided Data
                    </Button>
                    <Button
                        variant={scenario === "hidden_fire" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setScenario("hidden_fire")}
                        className={scenario === "hidden_fire" ? "bg-orange-500 hover:bg-orange-600" : "border-orange-300 text-orange-700 hover:bg-orange-50"}
                    >
                        🔥 Hidden Fire
                    </Button>
                    <Button
                        variant={scenario === "noise" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setScenario("noise")}
                        className={scenario === "noise" ? "bg-gray-600 hover:bg-gray-700" : ""}
                    >
                        📢 The Noise
                    </Button>
                </div>
                <span className="text-xs text-gray-500 ml-auto">
                    {scenario === "default" && "Original dataset with mixed tickets"}
                    {scenario === "hidden_fire" && "5 Enterprise tickets with SILENCE trap (should rank HIGH)"}
                    {scenario === "noise" && "150 Starter tickets with ANGRY messages (should rank LOW)"}
                </span>
            </div>

            <Tabs value={strategy} onValueChange={(v) => setStrategy(v as SortStrategy)}>
                <TabsList className="grid w-full max-w-md grid-cols-2">
                    <TabsTrigger value="sentiment">Legacy Sentiment</TabsTrigger>
                    <TabsTrigger value="priority">Ontop AI Risk</TabsTrigger>
                </TabsList>
            </Tabs>

            {/* Data Table */}
            <div className="rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow className="bg-gray-50">
                            <TableHead className="font-semibold">Ticket</TableHead>
                            <TableHead className="font-semibold">Client</TableHead>
                            <TableHead className="font-semibold text-center">Risk Factors</TableHead>
                            <TableHead className="font-semibold text-center">Sentiment</TableHead>
                            <TableHead className="font-semibold text-center">Priority</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {sortedTickets.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={5} className="text-center py-8 text-gray-500">
                                    No tickets found
                                </TableCell>
                            </TableRow>
                        ) : (
                            sortedTickets.map((ticket) => {
                                const hiddenFire = isHiddenFire(ticket);
                                const highRisk = isHighRisk(ticket);

                                return (
                                    <TableRow
                                        key={ticket.ticket_id}
                                        onClick={() => {
                                            setSelectedTicket(ticket);
                                            setIsModalOpen(true);
                                        }}
                                        className={`
                      cursor-pointer
                      ${highRisk && strategy === "priority" ? "bg-red-50" : ""}
                      hover:bg-gray-50 transition-colors
                    `}
                                    >
                                        {/* Ticket Column */}
                                        <TableCell className="max-w-xs">
                                            <div className="space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <code className="text-xs font-mono bg-gray-100 px-2 py-0.5 rounded">
                                                        {ticket.ticket_id.substring(0, 8)}
                                                    </code>
                                                    {hiddenFire && (
                                                        <Badge variant="destructive" className="text-xs gap-1">
                                                            <Flame className="h-3 w-3" />
                                                            Hidden Fire
                                                        </Badge>
                                                    )}
                                                </div>
                                                <p className="text-sm font-medium text-gray-900">
                                                    {truncateSubject(ticket.subject)}
                                                </p>
                                                <p className="text-xs text-gray-500 capitalize">
                                                    {ticket.category}
                                                </p>
                                            </div>
                                        </TableCell>

                                        {/* Client Column */}
                                        <TableCell>
                                            <div className="space-y-1">
                                                <code className="text-xs font-mono">{ticket.client_id}</code>
                                                <div>
                                                    <Badge className={getMRRBadgeColor(ticket.mrr)}>
                                                        {ticket.mrr ? `$${ticket.mrr.toFixed(0)}` : "No MRR"}
                                                    </Badge>
                                                </div>
                                            </div>
                                        </TableCell>

                                        {/* Risk Factors Column */}
                                        <TableCell>
                                            <div className="flex items-center justify-center gap-2">
                                                {ticket.is_recurrent && (
                                                    <div className="flex items-center gap-1 text-orange-600" title="Recurrent Issue">
                                                        <RotateCcw className="h-4 w-4" />
                                                        <span className="text-xs font-medium">Recurrent</span>
                                                    </div>
                                                )}
                                                {ticket.silence_days > 5 && (
                                                    <div className="flex items-center gap-1 text-purple-600" title={`${ticket.silence_days.toFixed(0)} days silence`}>
                                                        <Ghost className="h-4 w-4" />
                                                        <span className="text-xs font-medium">{ticket.silence_days.toFixed(0)}d</span>
                                                    </div>
                                                )}
                                                {!ticket.is_recurrent && ticket.silence_days <= 5 && (
                                                    <span className="text-xs text-gray-400">—</span>
                                                )}
                                            </div>
                                        </TableCell>

                                        {/* Sentiment Column */}
                                        <TableCell>
                                            <div className="flex justify-center">
                                                <Badge className={getSentimentColor(ticket.sentiment_score)}>
                                                    {ticket.sentiment_score !== undefined
                                                        ? ticket.sentiment_score.toFixed(2)
                                                        : "N/A"}
                                                </Badge>
                                            </div>
                                        </TableCell>

                                        {/* Priority Column */}
                                        <TableCell>
                                            <div className="flex justify-center">
                                                <Badge className={getPriorityColor(ticket.priority_score)}>
                                                    {ticket.priority_score.toFixed(1)}
                                                </Badge>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                );
                            })
                        )}
                    </TableBody>
                </Table>
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-3 gap-4 text-center text-sm">
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <p className="text-2xl font-bold text-gray-900">{tickets.length}</p>
                    <p className="text-gray-600">Total Open Tickets</p>
                </div>
                <div className="rounded-lg border border-orange-200 bg-orange-50 p-4">
                    <p className="text-2xl font-bold text-orange-900">
                        {tickets.filter((t) => t.priority_score >= 50).length}
                    </p>
                    <p className="text-orange-700">High Risk (Score ≥ 50)</p>
                </div>
                <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                    <p className="text-2xl font-bold text-red-900">
                        {tickets.filter(isHiddenFire).length}
                    </p>
                    <p className="text-red-700">🔥 Hidden Fire Tickets</p>
                </div>
            </div>

            <TicketDetailModal
                ticket={selectedTicket}
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
            />
        </div>
    );
}
