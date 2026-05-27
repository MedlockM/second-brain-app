import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

interface TermsPageProps {
  onBack?: () => void;
}

export default function TermsPage({ onBack }: TermsPageProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-950 dark:to-black">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Back button */}
        {onBack ? (
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white mb-8 transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
            <span>Back</span>
          </button>
        ) : (
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors mb-8"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Home</span>
          </Link>
        )}

        {/* Header */}
        <div className="mb-12">
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
            Terms of Service
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Last updated: January 2025
          </p>
        </div>

        {/* Content */}
        <div className="prose prose-lg dark:prose-invert max-w-none">
          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
              1. Acceptance of Terms
            </h2>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              By accessing and using PodQuiz ("the Service"), you accept and
              agree to be bound by these Terms of Service. If you do not agree
              to these terms, please do not use our Service.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
              2. Description of Service
            </h2>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              PodQuiz provides AI-powered podcast summarization and quiz
              generation services. The Service allows users to:
            </p>
            <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-2 ml-4">
              <li>Search and discover podcasts</li>
              <li>Generate AI summaries of podcast episodes</li>
              <li>Create interactive quizzes based on podcast content</li>
              <li>Submit and process media links for transcription and artifacts</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
              3. User Accounts
            </h2>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              To use certain features of the Service, you must create an
              account. You are responsible for:
            </p>
            <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-2 ml-4">
              <li>
                Maintaining the confidentiality of your account credentials
              </li>
              <li>All activities that occur under your account</li>
              <li>Notifying us immediately of any unauthorized use</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
              4. Billing and Payments
            </h2>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              The Service operates on a minutes-based billing model. Users can
              purchase minutes through subscriptions or minute packs. All
              payments are processed through Stripe.
            </p>
            <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-2 ml-4">
              <li>
                Subscription fees are billed in advance on a monthly or annual
                basis
              </li>
              <li>Minute packs are one-time purchases and do not expire</li>
              <li>Refunds are handled on a case-by-case basis</li>
              <li>
                We reserve the right to change pricing with 30 days notice
              </li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
              5. Acceptable Use
            </h2>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              You agree not to:
            </p>
            <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-2 ml-4">
              <li>Use the Service for any unlawful purpose</li>
              <li>Attempt to gain unauthorized access to our systems</li>
              <li>Interfere with or disrupt the Service</li>
              <li>Reproduce, duplicate, or resell any part of the Service</li>
              <li>
                Use automated systems to access the Service without permission
              </li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
              6. Intellectual Property
            </h2>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              The Service and its original content, features, and functionality
              are owned by PodQuiz and are protected by international copyright,
              trademark, and other intellectual property laws.
            </p>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              Podcast content summarized through our Service remains the
              intellectual property of its respective owners. We do not claim
              ownership of any podcast content.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
              7. Limitation of Liability
            </h2>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              To the maximum extent permitted by law, PodQuiz shall not be
              liable for any indirect, incidental, special, consequential, or
              punitive damages resulting from your use of the Service.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
              8. Changes to Terms
            </h2>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              We reserve the right to modify these Terms at any time. We will
              notify users of any material changes via email or through the
              Service. Continued use of the Service after changes constitutes
              acceptance of the new Terms.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
              9. Contact Us
            </h2>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              If you have any questions about these Terms, please contact us at:
            </p>
            <p className="text-gray-700 dark:text-gray-300">
              <a
                href="mailto:support@podquiz.io"
                className="text-blue-600 dark:text-blue-400 hover:underline"
              >
                support@podquiz.io
              </a>
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
