import React from "react";

export function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <svg className="w-16 h-16 text-ndai-300 mx-auto mb-4" viewBox="0 0 48 48" fill="none">
          <path d="M24 4L6 12v12c0 11 8 18 18 22 10-4 18-11 18-22V12L24 4z" fill="currentColor" />
          <circle cx="24" cy="22" r="3.5" fill="none" stroke="white" strokeWidth="1.5" />
          <rect x="22.75" y="25" width="2.5" height="4" rx="0.75" fill="white" />
        </svg>
        <h1 className="text-4xl font-bold text-gray-300 mb-2">404</h1>
        <p className="text-gray-500 mb-6">Page not found</p>
        <a
          href="#/login"
          className="px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 font-medium text-sm transition-colors"
        >
          Go to Dashboard
        </a>
      </div>
    </div>
  );
}
