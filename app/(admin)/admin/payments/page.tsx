"use client";

import { useEffect, useState } from "react";
import { adminApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search, CreditCard, Download, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { format } from "date-fns";
import { Button } from "@/components/ui/button";

export default function PaymentsAdminPage() {
  const [payments, setPayments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    const fetchPayments = async () => {
      try {
        const data = await adminApi.getPayments();
        setPayments(data);
      } catch (err: any) {
        setError(err.message || "Failed to load payments");
      } finally {
        setLoading(false);
      }
    };
    fetchPayments();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative" role="alert">
        <strong className="font-bold">Error! </strong>
        <span className="block sm:inline">{error}</span>
      </div>
    );
  }

  const filteredPayments = payments.filter((p: any) => {
    const matchesSearch = 
      p.reference.toLowerCase().includes(search.toLowerCase()) ||
      p.user?.username?.toLowerCase().includes(search.toLowerCase()) ||
      p.user?.email?.toLowerCase().includes(search.toLowerCase());
      
    const matchesStatus = statusFilter === "all" || p.status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  // Calculate summary metrics
  const totalRevenue = payments
    .filter(p => p.status === 'success')
    .reduce((sum, p) => sum + parseFloat(p.amount), 0);
    
  const successfulCount = payments.filter(p => p.status === 'success').length;
  const pendingCount = payments.filter(p => p.status === 'pending').length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Payments & Revenue</h1>
          <p className="text-gray-500 mt-1">Track subscription payments and financial metrics.</p>
        </div>
        <Button variant="outline" className="flex items-center gap-2">
          <Download className="h-4 w-4" />
          Export CSV
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="border-none shadow-sm">
          <CardContent className="p-6">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm font-medium text-gray-500">Total Collected</p>
                <p className="text-3xl font-bold text-gray-900 mt-2">
                  ₦{(totalRevenue / 1000).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}k
                </p>
              </div>
              <div className="p-3 bg-primary/10 rounded-full text-primary">
                <CreditCard className="h-5 w-5" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <span className="text-emerald-600 font-medium flex items-center">
                <ArrowUpRight className="h-4 w-4 mr-1" />
                12.5%
              </span>
              <span className="text-gray-500 ml-2">from last month</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-none shadow-sm">
          <CardContent className="p-6">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm font-medium text-gray-500">Successful Transactions</p>
                <p className="text-3xl font-bold text-gray-900 mt-2">{successfulCount}</p>
              </div>
              <div className="p-3 bg-emerald-100 rounded-full text-emerald-600">
                <ArrowUpRight className="h-5 w-5" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-none shadow-sm">
          <CardContent className="p-6">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm font-medium text-gray-500">Pending Transactions</p>
                <p className="text-3xl font-bold text-gray-900 mt-2">{pendingCount}</p>
              </div>
              <div className="p-3 bg-amber-100 rounded-full text-amber-600">
                <ArrowDownRight className="h-5 w-5" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-none shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
            <div className="relative w-full sm:max-w-xs">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <Input 
                placeholder="Search reference or user..." 
                className="pl-9"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="flex gap-2 w-full sm:w-auto">
              <select 
                className="flex h-10 w-full sm:w-[150px] items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="all">All Statuses</option>
                <option value="success">Success</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-y border-gray-200">
                <tr>
                  <th className="px-4 py-3 font-medium">Reference</th>
                  <th className="px-4 py-3 font-medium">User</th>
                  <th className="px-4 py-3 font-medium">Amount</th>
                  <th className="px-4 py-3 font-medium">Duration</th>
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredPayments.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                      No payments found matching your filters.
                    </td>
                  </tr>
                ) : (
                  filteredPayments.map((payment) => (
                    <tr key={payment.id} className="hover:bg-gray-50">
                      <td className="px-4 py-4">
                        <span className="font-mono text-xs text-gray-600 bg-gray-100 px-2 py-1 rounded">
                          {payment.reference}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <div className="font-medium text-gray-900">{payment.user?.name || payment.user?.username}</div>
                        <div className="text-gray-500 text-xs">{payment.user?.email}</div>
                      </td>
                      <td className="px-4 py-4 font-medium text-gray-900">
                        {payment.currency} {parseFloat(payment.amount).toLocaleString()}
                      </td>
                      <td className="px-4 py-4 text-gray-500">
                        {payment.subscription_months} month{payment.subscription_months > 1 ? 's' : ''}
                      </td>
                      <td className="px-4 py-4 text-gray-500 text-xs whitespace-nowrap">
                        {format(new Date(payment.created_at), 'MMM d, yyyy h:mm a')}
                      </td>
                      <td className="px-4 py-4 text-right">
                        {payment.status === 'success' ? (
                          <Badge className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100 border-emerald-200">Success</Badge>
                        ) : payment.status === 'failed' ? (
                          <Badge variant="destructive">Failed</Badge>
                        ) : (
                          <Badge variant="secondary" className="bg-amber-100 text-amber-800 border-amber-200 hover:bg-amber-100">Pending</Badge>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
