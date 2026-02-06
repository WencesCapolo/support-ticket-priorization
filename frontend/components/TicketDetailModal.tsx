import { Ticket } from "@/lib/types";
import { X, RotateCcw, Clock, ShieldCheck, Flame } from "lucide-react";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

interface TicketDetailModalProps {
    ticket: Ticket | null;
    isOpen: boolean;
    onClose: () => void;
}

export function TicketDetailModal({ ticket, isOpen, onClose }: TicketDetailModalProps) {
    if (!isOpen || !ticket) return null;

    // Derived State for "Why" Factors
    const isHighMRR = ticket.mrr && ticket.mrr > 3000;
    const isSilenced = ticket.silence_days > 0;
    const isRecurrent = ticket.is_recurrent;

    // Determine priority color for the new 0-100 scale
    const getPriorityColor = (score: number): string => {
        if (score >= 70) return "text-red-600";
        if (score >= 50) return "text-orange-500";
        if (score >= 30) return "text-yellow-600";
        return "text-gray-600";
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div
                className="bg-white rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden animate-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-mono font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                                {ticket.ticket_id}
                            </span>
                            <Badge variant="outline" className="text-xs font-normal">
                                {ticket.category}
                            </Badge>
                        </div>
                        <h2 className="text-xl font-bold text-gray-900 line-clamp-1">
                            {ticket.subject || "No Subject"}
                        </h2>
                    </div>
                    <Button variant="ghost" size="icon" onClick={onClose} className="rounded-full hover:bg-gray-200">
                        <X className="h-5 w-5 text-gray-500" />
                    </Button>
                </div>

                {/* Content */}
                <div className="p-6 space-y-8">

                    {/* The "Why" Section */}
                    <div className="space-y-4">
                        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                            Why this priority?
                        </h3>

                        <div className="grid gap-3">
                            {/* Recurrence Warning */}
                            {isRecurrent && (
                                <div className="flex items-start gap-4 p-4 rounded-lg bg-orange-50 border border-orange-100">
                                    <div className="p-2 bg-orange-100 rounded-lg">
                                        <RotateCcw className="h-5 w-5 text-orange-600" />
                                    </div>
                                    <div>
                                        <h4 className="font-semibold text-gray-900">Recurrence Detected</h4>
                                        <p className="text-sm text-gray-600 mt-1">
                                            This issue has happened <span className="font-bold text-orange-700">{ticket.recurrence_count} times</span> recently.
                                            Chronic issues risk client health.
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Wait Time Warning */}
                            {isSilenced && (
                                <div className="flex items-start gap-4 p-4 rounded-lg bg-purple-50 border border-purple-100">
                                    <div className="p-2 bg-purple-100 rounded-lg">
                                        <Clock className="h-5 w-5 text-purple-600" />
                                    </div>
                                    <div>
                                        <h4 className="font-semibold text-gray-900">Customer Waiting</h4>
                                        <p className="text-sm text-gray-600 mt-1">
                                            Customer has been silent for <span className="font-bold text-purple-700">{ticket.silence_days.toFixed(0)} days</span>.
                                            Response is overdue.
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Enterprise Client Badge */}
                            {isHighMRR && (
                                <div className="flex items-start gap-4 p-4 rounded-lg bg-blue-50 border border-blue-100">
                                    <div className="p-2 bg-blue-100 rounded-lg">
                                        <ShieldCheck className="h-5 w-5 text-blue-600" />
                                    </div>
                                    <div>
                                        <h4 className="font-semibold text-gray-900">Enterprise Client</h4>
                                        <p className="text-sm text-gray-600 mt-1">
                                            High-value account (<span className="font-bold text-blue-700">${ticket.mrr?.toFixed(0)}/mo</span>).
                                            Priority handling required.
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Fallback if no specific triggers */}
                            {!isRecurrent && !isSilenced && !isHighMRR && (
                                <div className="p-4 rounded-lg bg-gray-50 border border-gray-100 text-center text-gray-500 text-sm">
                                    No critical risk factors detected. Standard handling applies.
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Additional Details Grid */}
                    <div className="pt-6 border-t border-gray-100 grid grid-cols-2 gap-6">
                        <div>
                            <span className="text-xs text-gray-500 block mb-1">Sentiment Score</span>
                            <div className="flex items-center gap-2">
                                <span className={`text-lg font-bold ${ticket.sentiment_score < 0 ? 'text-red-600' : 'text-green-600'
                                    }`}>
                                    {ticket.sentiment_score.toFixed(2)}
                                </span>
                                <span className="text-xs text-gray-400">(TextBlob Polarity)</span>
                            </div>
                        </div>
                        <div>
                            <span className="text-xs text-gray-500 block mb-1">Overall Priority Score</span>
                            <div className="flex items-center gap-2">
                                <span className={`text-lg font-bold ${getPriorityColor(ticket.priority_score)}`}>
                                    {ticket.priority_score.toFixed(1)}
                                </span>
                                <span className="text-xs text-gray-400">/ 100</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Footer Controls */}
                <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex justify-end gap-3">
                    <Button variant="outline" onClick={onClose}>
                        Close
                    </Button>
                    <Button className="bg-blue-600 hover:bg-blue-700">
                        Open in Helpdesk
                    </Button>
                </div>
            </div>
        </div>
    );
}
