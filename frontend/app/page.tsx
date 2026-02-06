import TicketDashboard from "@/components/TicketDashboard";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="container mx-auto px-4 py-12">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <svg
                className="h-6 w-6 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
            </div>
            <h1 className="text-4xl font-bold text-gray-900">
              Support Ticket Command Center
            </h1>
          </div>
          <p className="text-lg text-gray-600 ml-13">
            AI-powered risk prioritization vs. legacy sentiment-based sorting
          </p>
        </div>

        {/* Dashboard Component */}
        <div className="bg-white rounded-xl shadow-lg p-8">
          <TicketDashboard />
        </div>

        {/* Footer Info */}
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>
            Backend API: <code className="bg-gray-200 px-2 py-1 rounded">http://localhost:8000</code>
          </p>
        </div>
      </div>
    </div>
  );
}

