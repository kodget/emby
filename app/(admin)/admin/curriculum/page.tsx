"use client";

import { useEffect, useState } from "react";
import { adminApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, Building, GraduationCap, BookOpen, ChevronRight } from "lucide-react";
import { Input } from "@/components/ui/input";

type CurriculumData = {
  schools: any[];
  classes: any[];
  subjects: any[];
};

export default function CurriculumAdminPage() {
  const [data, setData] = useState<CurriculumData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const curriculumData = await adminApi.getCurriculum();
        setData(curriculumData);
      } catch (err: any) {
        setError(err.message || "Failed to load curriculum data");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative" role="alert">
        <strong className="font-bold">Error! </strong>
        <span className="block sm:inline">{error}</span>
      </div>
    );
  }

  const filteredSchools = data.schools.filter((s: any) => 
    s.name.toLowerCase().includes(search.toLowerCase())
  );
  
  const filteredClasses = data.classes.filter((c: any) => 
    c.school_name.toLowerCase().includes(search.toLowerCase()) ||
    (c.set_name && c.set_name.toLowerCase().includes(search.toLowerCase())) ||
    c.code.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Curriculum Management</h1>
          <p className="text-gray-500 mt-1">Manage schools, classes, and subjects across the platform.</p>
        </div>
      </div>

      <div className="relative w-full sm:max-w-md">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
        <Input 
          placeholder="Search schools or classes..." 
          className="pl-9"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Schools List */}
        <Card className="border-none shadow-sm lg:col-span-1 h-[600px] flex flex-col">
          <CardHeader className="pb-3 border-b">
            <div className="flex items-center gap-2">
              <Building className="h-5 w-5 text-primary" />
              <CardTitle className="text-lg">Schools ({data.schools.length})</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-0 overflow-y-auto flex-1">
            <div className="divide-y">
              {filteredSchools.length === 0 ? (
                <div className="p-6 text-center text-sm text-gray-500">No schools found.</div>
              ) : (
                filteredSchools.map((school: any) => (
                  <div key={school.id} className="p-4 hover:bg-gray-50 transition-colors flex items-center justify-between cursor-pointer">
                    <span className="font-medium text-sm text-gray-900">{school.name}</span>
                    <ChevronRight className="h-4 w-4 text-gray-400" />
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Classes List */}
        <Card className="border-none shadow-sm lg:col-span-2 h-[600px] flex flex-col">
          <CardHeader className="pb-3 border-b flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <GraduationCap className="h-5 w-5 text-emerald-600" />
              <CardTitle className="text-lg">Active Classes ({data.classes.length})</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-0 overflow-y-auto flex-1">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-500 uppercase bg-gray-50 sticky top-0 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 font-medium">Class Code</th>
                  <th className="px-4 py-3 font-medium">School / Set</th>
                  <th className="px-4 py-3 font-medium">Members</th>
                  <th className="px-4 py-3 font-medium">Class Heads</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredClasses.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                      No classes found.
                    </td>
                  </tr>
                ) : (
                  filteredClasses.map((cls: any) => (
                    <tr key={cls.id} className="hover:bg-gray-50">
                      <td className="px-4 py-4">
                        <Badge variant="outline" className="font-mono bg-white">{cls.code}</Badge>
                      </td>
                      <td className="px-4 py-4">
                        <div className="font-medium text-gray-900">{cls.school_name}</div>
                        <div className="text-gray-500 text-xs">{cls.set_name || 'General'}</div>
                      </td>
                      <td className="px-4 py-4">
                        <span className="font-medium">{cls.member_count}</span> students
                      </td>
                      <td className="px-4 py-4 text-xs text-gray-500">
                        {cls.class_heads && cls.class_heads.length > 0 ? (
                          <div className="flex flex-col gap-1">
                            {cls.class_heads.map((head: any) => (
                              <span key={head.id}>{head.name}</span>
                            ))}
                          </div>
                        ) : (
                          <span className="italic text-gray-400">None assigned</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>

      </div>
      
      {/* Subjects section */}
      <Card className="border-none shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-amber-600" />
            <CardTitle className="text-lg">Platform Subjects ({data.subjects.length})</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {data.subjects.length === 0 ? (
              <span className="text-sm text-gray-500">No subjects registered yet.</span>
            ) : (
              data.subjects.map((sub: any) => (
                <Badge key={sub.id} variant="secondary" className="px-3 py-1 bg-amber-50 text-amber-900 hover:bg-amber-100 border-none">
                  {sub.name}
                </Badge>
              ))
            )}
          </div>
        </CardContent>
      </Card>
      
    </div>
  );
}
