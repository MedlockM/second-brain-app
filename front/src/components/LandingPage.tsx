import { Features } from "./ui/features";
import { Headphones, Sparkles, Zap, ArrowRight, DollarSign } from "lucide-react";

const features = [
  {
    id: 1,
    icon: Headphones,
    title: "Listen to Your Favorite Podcasts",
    description:
      "Connect your Spotify account and access all your podcast subscriptions in one place. Never miss an episode again.",
    image: "https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=800&h=600&fit=crop",
  },
  {
    id: 2,
    icon: Sparkles,
    title: "AI-Powered Summaries",
    description:
      "Get instant, intelligent summaries of podcast episodes. Save time while staying informed about the content that matters to you.",
    image: "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=800&h=600&fit=crop",
  },
  {
    id: 3,
    icon: Zap,
    title: "Quick & Efficient",
    description:
      "Browse through summaries, search for specific topics, and jump to the parts that interest you most. Your time is valuable.",
    image: "https://images.unsplash.com/photo-1589903308904-1010c2294adc?w=800&h=600&fit=crop",
  },
];

interface LandingPageProps {
  onGetStarted: () => void;
  onPricingClick?: () => void;
}

export default function LandingPage({ onGetStarted, onPricingClick }: LandingPageProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Header Navigation */}
      <nav className="absolute top-0 right-0 left-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-end items-center h-16">
            {onPricingClick && (
              <button
                onClick={onPricingClick}
                className="flex items-center space-x-2 px-4 py-2 text-sm font-semibold text-gray-700 hover:text-blue-600 transition-colors"
              >
                <DollarSign className="h-4 w-4" />
                <span>Pricing</span>
              </button>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-16 text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 mb-8 bg-blue-100 dark:bg-blue-900/30 rounded-full text-blue-700 dark:text-blue-300 text-sm font-medium">
            <Sparkles size={16} className="text-blue-500" />
            <span>AI-Powered Podcast Summaries</span>
          </div>

          {/* Main Heading */}
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-gray-900 dark:text-white mb-6 leading-tight">
            Transform Your
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600">
              Podcast Experience
            </span>
          </h1>

          {/* Subheading */}
          <p className="text-xl md:text-2xl text-gray-600 dark:text-gray-300 mb-12 max-w-3xl mx-auto">
            Get intelligent summaries of your favorite podcast episodes.
            Save time, stay informed, and never miss the key insights.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <button
              onClick={onGetStarted}
              className="group px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 flex items-center gap-2"
            >
              Get Started Free
              <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
            </button>
            <button
              onClick={onGetStarted}
              className="px-8 py-4 bg-white dark:bg-gray-800 text-gray-900 dark:text-white font-semibold rounded-lg shadow-md hover:shadow-lg border border-gray-200 dark:border-gray-700 transform hover:scale-105 transition-all duration-200"
            >
              Sign In
            </button>
          </div>

          {/* Trust Badge */}
          <div className="mt-16 flex flex-col items-center gap-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Trusted by podcast enthusiasts worldwide
            </p>
            <div className="flex items-center gap-6 text-gray-400">
              <div className="flex items-center gap-2">
                <Headphones size={20} />
                <span className="text-sm">Spotify Integration</span>
              </div>
              <div className="flex items-center gap-2">
                <Sparkles size={20} />
                <span className="text-sm">AI Summaries</span>
              </div>
              <div className="flex items-center gap-2">
                <Zap size={20} />
                <span className="text-sm">Instant Results</span>
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
            Join thousands of users who are already saving time with AI-powered podcast summaries.
          </p>
          <button
            onClick={onGetStarted}
            className="group px-8 py-4 bg-white text-blue-600 font-semibold rounded-lg shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 flex items-center gap-2 mx-auto"
          >
            Start Free Today
            <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
          </button>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-gray-200 dark:border-gray-800 mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <p className="text-center text-gray-500 dark:text-gray-400 text-sm">
            © 2024 Media Summarizer. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
