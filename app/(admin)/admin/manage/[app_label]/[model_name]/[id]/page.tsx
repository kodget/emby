"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { adminApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Save } from "lucide-react";
import Link from "next/link";
import { Label } from "@/components/ui/label";

export default function UniversalAdminFormPage() {
  const params = useParams();
  const router = useRouter();
  const appLabel = params.app_label as string;
  const modelName = params.model_name as string;
  const id = params.id as string;
  const isNew = id === 'new';

  const [schema, setSchema] = useState<any>(null);
  const [formData, setFormData] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      setError(null);
      try {
        // Find schema
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

        // If editing, fetch data
        if (!isNew) {
           const record = await adminApi.getAdminDataDetail(appLabel, modelName, id);
           setFormData(record);
        } else {
           // Initialize default values based on schema
           const initialData: any = {};
           foundSchema.fields.forEach((f: any) => {
              if (f.many_to_many) initialData[f.name] = [];
              else if (f.type === "BooleanField") initialData[f.name] = false;
              else initialData[f.name] = "";
           });
           setFormData(initialData);
        }
      } catch (err: any) {
        setError(err.message || "Failed to load data");
      } finally {
        setLoading(false);
      }
    };
    
    init();
  }, [appLabel, modelName, id, isNew]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (isNew) {
         await adminApi.createAdminData(appLabel, modelName, formData);
      } else {
         await adminApi.updateAdminData(appLabel, modelName, id, formData);
      }
      router.push(`/admin/manage/${appLabel}/${modelName}`);
    } catch (err: any) {
       setError(err.message || "Failed to save record");
       setSaving(false);
    }
  };

  const handleFieldChange = (name: string, value: any) => {
     setFormData((prev: Record<string, any>) => ({ ...prev, [name]: value }));
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error && !schema) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative">
        <strong className="font-bold">Error! </strong>
        <span className="block sm:inline">{error}</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-4">
        <Link href={`/admin/manage/${appLabel}/${modelName}`}>
          <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
            <span>{appLabel.toUpperCase()}</span>
            <span>/</span>
            <span>{schema.verbose_name_plural}</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            {isNew ? `Add ${schema.verbose_name}` : `Edit ${schema.verbose_name} #${id}`}
          </h1>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative text-sm">
          {error}
        </div>
      )}

      <Card className="border-none shadow-sm">
        <form onSubmit={handleSubmit}>
          <CardContent className="p-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {schema.fields.map((field: any) => {
                if (field.auto_created && field.name === 'id') return null; // Hide auto PK
                
                return (
                  <div key={field.name} className={`space-y-2 ${field.type === 'TextField' ? 'md:col-span-2' : ''}`}>
                    <Label htmlFor={field.name} className="flex items-center gap-2">
                      {field.verbose_name}
                      {field.is_relation && <span className="text-[10px] bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded uppercase font-mono">{field.type}</span>}
                    </Label>
                    
                    {field.choices ? (
                      <select
                        id={field.name}
                        value={formData[field.name] || ''}
                        onChange={(e) => handleFieldChange(field.name, e.target.value)}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                      >
                        <option value="">Select...</option>
                        {field.choices.map((c: any) => (
                          <option key={c.value} value={c.value}>{c.label}</option>
                        ))}
                      </select>
                    ) : field.type === 'BooleanField' ? (
                      <div className="flex items-center h-10">
                        <input
                          type="checkbox"
                          id={field.name}
                          checked={!!formData[field.name]}
                          onChange={(e) => handleFieldChange(field.name, e.target.checked)}
                          className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                      </div>
                    ) : field.type === 'TextField' ? (
                      <textarea
                        id={field.name}
                        value={formData[field.name] || ''}
                        onChange={(e) => handleFieldChange(field.name, e.target.value)}
                        className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                      />
                    ) : (
                      <Input
                        id={field.name}
                        type={field.type === 'IntegerField' || field.type === 'DecimalField' ? 'number' : field.type === 'DateTimeField' || field.type === 'DateField' ? 'text' : 'text'}
                        value={formData[field.name] || ''}
                        onChange={(e) => handleFieldChange(field.name, e.target.value)}
                        placeholder={field.is_relation ? `Enter ${field.related_model || ''} ID` : ''}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
          <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex justify-end gap-3 rounded-b-xl">
            <Link href={`/admin/manage/${appLabel}/${modelName}`}>
               <Button type="button" variant="outline">Cancel</Button>
            </Link>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
