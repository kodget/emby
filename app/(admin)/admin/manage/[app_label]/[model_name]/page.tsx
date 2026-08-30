"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { adminApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search, Plus, Trash2, Edit2, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { format } from "date-fns";

export default function UniversalAdminPage() {
  const params = useParams();
  const router = useRouter();
  const appLabel = params.app_label as string;
  const modelName = params.model_name as string;

  const [schema, setSchema] = useState<any>(null);
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Pagination & Search
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const limit = 50;

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      setError(null);
      try {
        // Find schema for this specific model
        const fullSchema = await adminApi.getSchema();
        let foundSchema = null;
        for (const app of fullSchema) {
          if (app.app_label === appLabel) {
            const model = app.models.find((m: any) => m.model_name === modelName);
            if (model) foundSchema = model;
          }
        }
        
        if (!foundSchema) {
           setError(`Schema not found for ${appLabel}.${modelName}`);
           setLoading(false);
           return;
        }
        
        setSchema(foundSchema);

        // Fetch data
        const res = await adminApi.getAdminDataList(appLabel, modelName, page);
        setData(res.results);
        setTotal(res.total);
      } catch (err: any) {
        setError(err.message || "Failed to load data");
      } finally {
        setLoading(false);
      }
    };
    
    init();
  }, [appLabel, modelName, page]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error || !schema) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative">
        <strong className="font-bold">Error! </strong>
        <span className="block sm:inline">{error}</span>
      </div>
    );
  }

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this item?")) return;
    try {
      await adminApi.deleteAdminData(appLabel, modelName, id);
      setData(data.filter(item => item.id !== id));
      setTotal(t => t - 1);
    } catch (err: any) {
      alert("Failed to delete: " + err.message);
    }
  };

  // Determine which fields to show in the table (max 6 columns for neatness)
  const tableFields = schema.fields
    .filter((f: any) => !f.many_to_many)
    .slice(0, 6);

  const renderCell = (field: any, item: any) => {
    const val = item[field.name];
    if (val === null || val === undefined) return <span className="text-gray-400">-</span>;
    
    if (typeof val === 'boolean') {
      return (
        <span className={`px-2 py-1 rounded text-xs font-medium ${val ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
          {val ? 'Yes' : 'No'}
        </span>
      );
    }
    
    if (field.is_relation && field.many_to_one) {
       return <span className="text-primary truncate max-w-[200px] block" title={item[`${field.name}_display`]}>{item[`${field.name}_display`] || val}</span>;
    }

    if (field.type === "DateTimeField") {
       try { return format(new Date(val), 'MMM d, yyyy h:mm a'); } catch (e) { return val; }
    }
    if (field.type === "DateField") {
       try { return format(new Date(val), 'MMM d, yyyy'); } catch (e) { return val; }
    }

    const strVal = String(val);
    if (strVal.length > 50) return <span title={strVal}>{strVal.substring(0, 50)}...</span>;
    return strVal;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
            <span>{appLabel.toUpperCase()}</span>
            <span>/</span>
            <span className="text-gray-900 font-medium">{schema.verbose_name_plural}</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Manage {schema.verbose_name_plural}</h1>
        </div>
        <Link href={`/admin/manage/${appLabel}/${modelName}/new`}>
          <Button className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Add {schema.verbose_name}
          </Button>
        </Link>
      </div>

      <Card className="border-none shadow-sm">
        <CardHeader className="pb-4 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <div className="relative w-full max-w-sm">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <Input placeholder="Search records..." className="pl-9" />
            </div>
            <div className="text-sm text-gray-500 font-medium">
               {total} {total === 1 ? 'record' : 'records'}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 font-medium w-16">ID</th>
                  {tableFields.map((f: any) => (
                    <th key={f.name} className="px-6 py-3 font-medium">
                      {f.verbose_name}
                    </th>
                  ))}
                  <th className="px-6 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {data.length === 0 ? (
                  <tr>
                    <td colSpan={tableFields.length + 2} className="px-6 py-8 text-center text-gray-500">
                      No {schema.verbose_name_plural.toLowerCase()} found.
                    </td>
                  </tr>
                ) : (
                  data.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 font-mono text-xs text-gray-500">
                        {item.id}
                      </td>
                      {tableFields.map((f: any) => (
                        <td key={f.name} className="px-6 py-4 text-gray-900">
                          {renderCell(f, item)}
                        </td>
                      ))}
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Link href={`/admin/manage/${appLabel}/${modelName}/${item.id}`}>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0 text-blue-600 hover:text-blue-700 hover:bg-blue-50">
                              <Edit2 className="h-4 w-4" />
                            </Button>
                          </Link>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleDelete(item.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          
          {/* Simple Pagination */}
          {total > limit && (
            <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 bg-gray-50">
               <Button 
                 variant="outline" 
                 size="sm" 
                 disabled={page === 1}
                 onClick={() => setPage(p => p - 1)}
               >
                 Previous
               </Button>
               <span className="text-sm text-gray-500">
                 Page {page} of {Math.ceil(total / limit)}
               </span>
               <Button 
                 variant="outline" 
                 size="sm" 
                 disabled={page >= Math.ceil(total / limit)}
                 onClick={() => setPage(p => p + 1)}
               >
                 Next
               </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
