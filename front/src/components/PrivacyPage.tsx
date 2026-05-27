import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-950 dark:to-black">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Back Button */}
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors mb-8"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Home</span>
        </Link>

        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 md:p-12">
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-8">
            Privacy Policy
          </h1>

          <div className="prose prose-gray dark:prose-invert max-w-none">
            <p className="text-gray-600 dark:text-gray-300 mb-6">
              <strong>Last updated:</strong> January 2025
            </p>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
                1. Introduction
              </h2>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                PodQuiz ("we", "our", or "us") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our podcast summarization service.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
                2. Information We Collect
              </h2>
              <h3 className="text-xl font-medium text-gray-800 dark:text-gray-200 mb-3">
                2.1 Information You Provide
              </h3>
              <ul className="list-disc list-inside text-gray-600 dark:text-gray-300 mb-4 space-y-2">
                <li>Account information (email address, password)</li>
                <li>Payment information (processed securely by Stripe)</li>
                <li>Podcast preferences and followed shows</li>
              </ul>

              <h3 className="text-xl font-medium text-gray-800 dark:text-gray-200 mb-3">
                2.2 Information Collected Automatically
              </h3>
              <ul className="list-disc list-inside text-gray-600 dark:text-gray-300 mb-4 space-y-2">
                <li>Usage data (episodes processed, features used)</li>
                <li>Device information (browser type, operating system)</li>
                <li>Log data (IP address, access times)</li>
              </ul>

              <h3 className="text-xl font-medium text-gray-800 dark:text-gray-200 mb-3">
                2.3 Third-Party Services
              </h3>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                We use third-party infrastructure and AI providers only for the data processing required by the service.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
                3. How We Use Your Information
              </h2>
              <ul className="list-disc list-inside text-gray-600 dark:text-gray-300 mb-4 space-y-2">
                <li>To provide and maintain our service</li>
                <li>To process podcast episodes and generate summaries</li>
                <li>To manage your account and subscriptions</li>
                <li>To send you service-related communications</li>
                <li>To improve our service and develop new features</li>
                <li>To detect and prevent fraud or abuse</li>
              </ul>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
                4. Data Sharing and Disclosure
              </h2>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                We do not sell your personal information. We may share your information with:
              </p>
              <ul className="list-disc list-inside text-gray-600 dark:text-gray-300 mb-4 space-y-2">
                <li><strong>Service providers:</strong> Stripe (payments), AWS (infrastructure), OpenAI (AI processing)</li>
                <li><strong>Legal requirements:</strong> When required by law or to protect our rights</li>
                <li><strong>Business transfers:</strong> In connection with a merger or acquisition</li>
              </ul>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
                5. Data Security
              </h2>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                We implement appropriate technical and organizational measures to protect your personal information, including encryption in transit (HTTPS) and at rest, secure authentication, and regular security audits.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
                6. Data Retention
              </h2>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                We retain your personal information for as long as your account is active or as needed to provide you services. You can request deletion of your account and associated data at any time.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
                7. Your Rights (GDPR)
              </h2>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                If you are in the European Economic Area, you have the right to:
              </p>
              <ul className="list-disc list-inside text-gray-600 dark:text-gray-300 mb-4 space-y-2">
                <li>Access your personal data</li>
                <li>Rectify inaccurate data</li>
                <li>Request erasure of your data</li>
                <li>Object to processing of your data</li>
                <li>Data portability</li>
                <li>Withdraw consent at any time</li>
              </ul>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                To exercise these rights, contact us at privacy@podquiz.io.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
                8. Cookies
              </h2>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                We use essential cookies for authentication and session management. We do not use tracking or advertising cookies.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
                9. Children's Privacy
              </h2>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                Our service is not intended for users under 16 years of age. We do not knowingly collect personal information from children.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
                10. Changes to This Policy
              </h2>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                We may update this Privacy Policy from time to time. We will notify you of any changes by posting the new policy on this page and updating the "Last updated" date.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
                11. Contact Us
              </h2>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                If you have any questions about this Privacy Policy, please contact us at:
              </p>
              <p className="text-gray-600 dark:text-gray-300">
                <strong>Email:</strong>{' '}
                <a
                  href="mailto:privacy@podquiz.io"
                  className="text-blue-600 dark:text-blue-400 hover:underline"
                >
                  privacy@podquiz.io
                </a>
              </p>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
