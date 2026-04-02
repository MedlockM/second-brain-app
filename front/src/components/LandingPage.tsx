import { Features } from "./ui/features";
import {
  Headphones,
  Sparkles,
  Zap,
  ArrowRight,
  BookOpen,
} from "lucide-react";
import Footer from "./Footer";

const features = [
  {
    id: 1,
    icon: Headphones,
    title: "Ingest Links From Anywhere",
    description:
      "Share or paste a media link and process it instantly. Keep your ingestion flow simple and platform-agnostic.",
    image:
      "https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=800&h=600&fit=crop",
  },
  {
    id: 2,
    icon: Sparkles,
    title: "AI-Powered Quizzes & Summaries",
    description:
      "Get quick quizzes and intelligent summaries of podcast episodes. Save time while staying informed about the content that matters to you.",
    image:
      "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=800&h=600&fit=crop",
  },
  {
    id: 3,
    icon: Zap,
    title: "Quick & Efficient",
    description:
      "Browse through summaries, search for specific topics, and jump to the parts that interest you most. Your time is valuable.",
    image:
      "https://images.unsplash.com/photo-1589903308904-1010c2294adc?w=800&h=600&fit=crop",
  },
];

interface LandingPageProps {
  onGetStarted: () => void;
}

export default function LandingPage({ onGetStarted }: LandingPageProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        {/* Logo */}
        <div className="absolute top-4 left-4 sm:top-6 sm:left-6 z-20">
          <div className="inline-flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center shadow-lg">
              <BookOpen className="h-7 w-7 text-white" />
            </div>
            <span className="text-2xl font-semibold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              PodQuiz
            </span>
          </div>
        </div>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 sm:pt-8 lg:pt-10 pb-16 flex flex-col items-start sm:items-center text-left sm:text-center min-h-[70vh] sm:min-h-0 justify-end sm:justify-start">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 mb-8 bg-blue-100 dark:bg-blue-900/30 rounded-full text-blue-700 dark:text-blue-300 text-sm font-medium">
            <Sparkles size={16} className="text-blue-500" />
            <span>AI-Powered Podcast Quizzes &amp; Summaries</span>
          </div>

          {/* Main Heading */}
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-gray-900 dark:text-white mb-6 leading-tight">
            Listen Once.
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600">
              Learn Twice.
            </span>
          </h1>

          {/* Subheading */}
          <p className="text-lg md:text-xl lg:text-2xl text-gray-700 dark:text-gray-300 mb-12 max-w-3xl mx-auto leading-relaxed">
            Get quick quizzes and intelligent summaries for your favorite
            podcast episodes as soon as you finish listening in your favorite
            app. Save time, stay informed, and never miss the key insights.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-start sm:justify-center items-stretch sm:items-center w-full sm:w-auto">
            <button
              onClick={onGetStarted}
              className="group w-full sm:w-auto px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 flex items-center justify-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 focus-visible:ring-offset-blue-50 dark:focus-visible:ring-blue-300 dark:focus-visible:ring-offset-gray-900"
            >
              Get Started Free
              <ArrowRight
                size={20}
                className="group-hover:translate-x-1 transition-transform"
              />
            </button>
            <button
              onClick={onGetStarted}
              className="w-full sm:w-auto px-6 py-3 bg-white/80 dark:bg-gray-800 text-gray-700 dark:text-gray-200 font-medium rounded-lg shadow-sm hover:shadow-md border border-gray-200/70 dark:border-gray-700/70 transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-blue-50 dark:focus-visible:ring-blue-300 dark:focus-visible:ring-offset-gray-900"
            >
              Sign In
            </button>
          </div>

          {/* Trust Badge */}
          <div className="mt-12 sm:mt-16 flex flex-col items-start sm:items-center gap-5 w-full">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Trusted by podcast enthusiasts worldwide
            </p>
            <div className="flex flex-col sm:flex-row sm:flex-wrap items-start sm:items-center justify-start sm:justify-center gap-3 sm:gap-6 text-gray-500 dark:text-gray-400">
              <div className="flex items-center gap-2">
                <Headphones size={18} />
                <span className="text-sm font-medium">Universal URL Ingestion</span>
              </div>
              <div className="flex items-center gap-2">
                <Sparkles size={18} />
                <span className="text-sm font-medium">AI Quizzes &amp; Summaries</span>
              </div>
              <div className="flex items-center gap-2">
                <Zap size={18} />
                <span className="text-sm font-medium">Instant Results</span>
              </div>
            </div>
          </div>
        </div>

        {/* Decorative Elements */}
        <div className="absolute top-0 left-0 w-72 h-72 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob pointer-events-none"></div>
        <div className="absolute top-0 right-0 w-72 h-72 bg-blue-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-2000 pointer-events-none"></div>
        <div className="absolute bottom-0 left-1/2 w-72 h-72 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-4000 pointer-events-none"></div>
      </div>

      {/* Features Section */}
      <Features
        primaryColor="blue-600"
        progressGradientLight="bg-gradient-to-r from-blue-500 to-purple-500"
        progressGradientDark="bg-gradient-to-r from-blue-400 to-purple-400"
        features={features}
      />

      {/* Footer CTA */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center">
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-12 shadow-2xl">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Ready to Get Started?
          </h2>
          <p className="text-xl text-blue-100 mb-8 max-w-2xl mx-auto">
            Join thousands of users who are already saving time with AI-powered
            podcast quizzes and summaries.
          </p>
          <button
            onClick={onGetStarted}
            className="group px-8 py-4 bg-white text-blue-600 font-semibold rounded-lg shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 flex items-center gap-2 mx-auto"
          >
            Start Free Today
            <ArrowRight
              size={20}
              className="group-hover:translate-x-1 transition-transform"
            />
          </button>
        </div>
      </div>

      {/* Footer */}
      <Footer />
    </div>
  );
}
