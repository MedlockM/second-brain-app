import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "../../src/contexts/AuthContext";
import { ArtifactService } from "../../src/services/artifactService";
import { getFriendlyErrorMessage } from "../../src/lib/getFriendlyErrorMessage";
import {
  BorderRadius,
  Colors,
  Shadows,
  Spacing,
  TouchTarget,
  Typography,
} from "../../src/constants/theme";

/**
 * Artifact detail screen.
 *
 * The backend writes each artifact as a JSON envelope:
 *   { artifact_id, scope, scope_id, artifact_type, generated_at, sources,
 *     source_count, generator_version, llm_usage, content }
 * where `content` is the actual structured payload, shaped per artifact_type.
 * Every shape carries a model-written `title` (task-270), and a quote carries the
 * corpus tag it came from:
 *
 * - summary_short:    { title, key_points: string[], takeaway }
 * - summary_detailed: { title, context, main_topics, key_points,
 *                       notable_quotes: [{text, source_ref}], conclusion }
 * - notes:            { objectives, concepts: [{term, explanation, importance}],
 *                       key_points, action_items, glossary: [{term, definition}] }
 * - flashcards:       { cards: [{question, answer}], card_count }
 * - quiz:             { questions: [{question, options: [{label, text}],
 *                       correct_answer, explanation}], question_count }
 *
 * This screen renders each shape with its own dedicated UI.
 */

type ArtifactKind =
  | "summary_short"
  | "summary_detailed"
  | "summary"
  | "notes"
  | "flashcards"
  | "quiz";

type LoadState =
  | { status: "loading" }
  | {
      status: "ready";
      type: ArtifactKind;
      payload: ArtifactPayload;
      sourceTitle: string | null;
      translation: TranslationInfo | null;
    }
  | { status: "error"; message: string }
  | { status: "not_ready"; message: string };

interface ArtifactPayload {
  generated_at?: string;
  source?: Record<string, unknown>;
  translation?: Record<string, unknown>;
  content?: unknown;
}

/** Translation provenance attached to a translated artifact (task-192). */
interface TranslationInfo {
  isTranslated: boolean;
  translatedFrom: string | null;
  targetLanguage: string | null;
  translationFailed: boolean;
}

/** English display names for the 11 V1 reading languages (task-189). */
const LANGUAGE_DISPLAY_NAMES: Record<string, string> = {
  fr: "French",
  en: "English",
  es: "Spanish",
  de: "German",
  it: "Italian",
  pt: "Portuguese",
  nl: "Dutch",
  ja: "Japanese",
  zh: "Chinese",
  ar: "Arabic",
  hi: "Hindi",
};

function languageDisplayName(code: string | null): string {
  if (!code) return "another language";
  const normalized = code.trim().toLowerCase();
  return LANGUAGE_DISPLAY_NAMES[normalized] ?? code.toUpperCase();
}

const KIND_LABEL: Record<ArtifactKind, string> = {
  summary_short: "Summary",
  summary_detailed: "Summary",
  summary: "Summary",
  notes: "Learning notes",
  flashcards: "Flashcards",
  quiz: "Quiz",
};

const KIND_ICON: Record<
  ArtifactKind,
  React.ComponentProps<typeof Ionicons>["name"]
> = {
  summary_short: "document-text-outline",
  summary_detailed: "document-text-outline",
  summary: "document-text-outline",
  notes: "book-outline",
  flashcards: "card-outline",
  quiz: "help-circle-outline",
};

export default function ArtifactDetailScreen() {
  const { artifactId } = useLocalSearchParams<{ artifactId: string }>();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const mountedRef = useRef(true);
  const scrollViewRef = useRef<ScrollView>(null);
  const artifactBodyTopRef = useRef(0);

  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const fetchContent = useCallback(async () => {
    if (!isAuthenticated || !artifactId) return;
    try {
      const response = await ArtifactService.getArtifactContent(artifactId);
      if (!mountedRef.current) return;
      const kind = normalizeArtifactKind(response.artifact_type);
      const payload = response.content as ArtifactPayload;
      const sourceTitle = pickSourceTitle(payload);
      const translation = pickTranslationInfo(payload);
      setState({
        status: "ready",
        type: kind,
        payload,
        sourceTitle,
        translation,
      });
    } catch (err) {
      if (!mountedRef.current) return;
      const httpStatus = (err as { status?: number } | undefined)?.status;
      if (httpStatus === 409) {
        setState({
          status: "not_ready",
          message:
            "This artifact isn't ready yet. Come back once generation completes.",
        });
        return;
      }
      setState({
        status: "error",
        message: getFriendlyErrorMessage(err, {
          fallback: "Unable to load this artifact.",
        }),
      });
    }
  }, [isAuthenticated, artifactId]);

  useEffect(() => {
    const timer = setTimeout(() => void fetchContent(), 0);
    return () => clearTimeout(timer);
  }, [fetchContent]);

  const handleReload = useCallback(() => {
    setState({ status: "loading" });
    void fetchContent();
  }, [fetchContent]);

  const handleBack = useCallback(() => {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace("/(tabs)/inbox");
    }
  }, [router]);

  const scrollToArtifactBody = useCallback(() => {
    requestAnimationFrame(() => {
      scrollViewRef.current?.scrollTo({
        y: artifactBodyTopRef.current,
        animated: true,
      });
    });
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <View style={styles.header}>
        <Pressable
          style={styles.headerButton}
          onPress={handleBack}
          accessibilityLabel="Go back"
          accessibilityRole="button"
          hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
        >
          <Ionicons name="arrow-back" size={24} color={Colors.textMain} />
        </Pressable>
        <View style={styles.headerSpacer} />
      </View>

      {state.status === "loading" ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      ) : state.status === "error" ? (
        <View style={styles.centered}>
          <Ionicons
            name="alert-circle"
            size={48}
            color={Colors.error}
            style={styles.failedIcon}
          />
          <Text style={styles.failedTitle}>Unable to load</Text>
          <Text style={styles.failedMessage}>{state.message}</Text>
          <Pressable
            style={styles.refreshButton}
            onPress={handleReload}
            accessibilityLabel="Retry loading artifact"
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.refreshButtonText}>Retry</Text>
          </Pressable>
        </View>
      ) : state.status === "not_ready" ? (
        <View style={styles.centered}>
          <Ionicons
            name="time-outline"
            size={48}
            color={Colors.textMuted}
            style={styles.failedIcon}
          />
          <Text style={styles.failedTitle}>Not ready yet</Text>
          <Text style={styles.failedMessage}>{state.message}</Text>
          <Pressable
            style={styles.refreshButton}
            onPress={handleReload}
            accessibilityLabel="Refresh artifact"
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.refreshButtonText}>Refresh</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView
          ref={scrollViewRef}
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.heroSection}>
            <View style={styles.kindChip}>
              <Ionicons
                name={KIND_ICON[state.type]}
                size={14}
                color={Colors.textMain}
              />
              <Text style={styles.kindChipText}>
                {KIND_LABEL[state.type].toUpperCase()}
              </Text>
            </View>
            {state.sourceTitle ? (
              <Text style={styles.heroTitle}>{state.sourceTitle}</Text>
            ) : null}
            <TranslationBadge translation={state.translation} />
          </View>

          <View
            onLayout={({ nativeEvent }) => {
              artifactBodyTopRef.current = nativeEvent.layout.y;
            }}
          >
            <ArtifactBody
              type={state.type}
              payload={state.payload}
              onQuizQuestionChange={scrollToArtifactBody}
            />
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

// --- Translation badge ---

function TranslationBadge({
  translation,
}: {
  translation: TranslationInfo | null;
}) {
  if (!translation) return null;

  // Translation was attempted but failed: surface the fallback to the user.
  if (translation.translationFailed) {
    const fromName = languageDisplayName(translation.translatedFrom);
    return (
      <View
        style={[styles.translationBadge, styles.translationBadgeFailed]}
        accessibilityRole="text"
        accessibilityLabel={`Translation unavailable. This content is shown in its original language, ${fromName}.`}
      >
        <Ionicons
          name="alert-circle-outline"
          size={14}
          color={Colors.error}
        />
        <Text style={[styles.translationBadgeText, styles.translationBadgeTextFailed]}>
          Translation unavailable — shown in {fromName}
        </Text>
      </View>
    );
  }

  if (!translation.isTranslated) return null;

  const fromName = languageDisplayName(translation.translatedFrom);
  return (
    <View
      style={styles.translationBadge}
      accessibilityRole="text"
      accessibilityLabel={`Translated from ${fromName}`}
    >
      <Ionicons name="language-outline" size={14} color={Colors.textMain} />
      <Text style={styles.translationBadgeText}>Translated from {fromName}</Text>
    </View>
  );
}

// --- Body switch ---

function ArtifactBody({
  type,
  payload,
  onQuizQuestionChange,
}: {
  type: ArtifactKind;
  payload: ArtifactPayload;
  onQuizQuestionChange: () => void;
}) {
  const content = (payload?.content ?? {}) as Record<string, unknown>;

  if (type === "summary_short" || type === "summary") {
    return <SummaryShortBody content={content} />;
  }
  if (type === "summary_detailed") {
    return <SummaryDetailedBody content={content} />;
  }
  if (type === "notes") {
    return <NotesBody content={content} />;
  }
  if (type === "flashcards") {
    return <FlashcardsBody content={content} />;
  }
  return (
    <QuizBody
      content={content}
      onQuestionChange={onQuizQuestionChange}
    />
  );
}

// --- Summary (short) ---

function SummaryShortBody({ content }: { content: Record<string, unknown> }) {
  const headline = pickString(content, ["title"]);
  const keyPoints = pickStringArray(content, ["key_points"]);
  const takeaway = pickString(content, ["takeaway"]);

  return (
    <View>
      {headline ? (
        <Text style={styles.summaryHeadline}>{headline}</Text>
      ) : null}
      {keyPoints && keyPoints.length > 0 ? (
        <Section title="Key points">
          <Bullets items={keyPoints} />
        </Section>
      ) : null}
      {takeaway ? (
        <Section title="Takeaway">
          <View style={styles.takeawayCard}>
            <Ionicons
              name="bulb-outline"
              size={18}
              color={Colors.onPrimary}
              style={styles.takeawayIcon}
            />
            <Text style={styles.takeawayText}>{takeaway}</Text>
          </View>
        </Section>
      ) : null}
    </View>
  );
}

// --- Summary (detailed) ---

function SummaryDetailedBody({
  content,
}: {
  content: Record<string, unknown>;
}) {
  const context = pickString(content, ["context"]);
  const mainTopics = pickStringArray(content, ["main_topics"]);
  const keyPoints = pickStringArray(content, ["key_points"]);
  // `notable_quotes` is a list of `{text, source_ref}` since task-270: the
  // reference is mandatory there because a quote is verbatim, so its origin is
  // checkable. Rendered next to the quote rather than dropped.
  const quotes = pickQuotes(content, ["notable_quotes"]);
  const conclusion = pickString(content, ["conclusion"]);

  return (
    <View>
      {context ? (
        <Section title="Context">
          <Text style={styles.body}>{context}</Text>
        </Section>
      ) : null}
      {mainTopics && mainTopics.length > 0 ? (
        <Section title="Main topics">
          <View style={styles.topicChipsRow}>
            {mainTopics.map((topic, i) => (
              <View key={`topic-${i}`} style={styles.topicChip}>
                <Text style={styles.topicChipText}>{topic}</Text>
              </View>
            ))}
          </View>
        </Section>
      ) : null}
      {keyPoints && keyPoints.length > 0 ? (
        <Section title="Key points">
          <Bullets items={keyPoints} />
        </Section>
      ) : null}
      {quotes && quotes.length > 0 ? (
        <Section title="Notable quotes">
          {quotes.map((q, i) => (
            <View key={`quote-${i}`} style={styles.quoteCard}>
              <Text style={styles.quoteMark}>“</Text>
              <Text style={styles.quoteText}>{q.text}</Text>
              {q.sourceRef ? (
                <Text style={styles.quoteSourceRef}>{q.sourceRef}</Text>
              ) : null}
            </View>
          ))}
        </Section>
      ) : null}
      {conclusion ? (
        <Section title="Conclusion">
          <Text style={styles.body}>{conclusion}</Text>
        </Section>
      ) : null}
    </View>
  );
}

// --- Notes ---

function NotesBody({ content }: { content: Record<string, unknown> }) {
  const objectives = pickStringArray(content, ["objectives"]);
  const concepts = pickConceptArray(content);
  const keyPoints = pickStringArray(content, ["key_points"]);
  const actionItems = pickStringArray(content, ["action_items"]);
  const glossary = pickGlossaryArray(content);

  return (
    <View>
      {objectives && objectives.length > 0 ? (
        <Section title="Objectives">
          <Bullets items={objectives} />
        </Section>
      ) : null}
      {concepts && concepts.length > 0 ? (
        <Section title="Concepts">
          {concepts.map((c, i) => (
            <View key={`concept-${i}`} style={styles.conceptCard}>
              <View style={styles.conceptHeader}>
                <Text style={styles.conceptTerm}>{c.term}</Text>
                {c.importance ? (
                  <View
                    style={[
                      styles.importanceBadge,
                      c.importance.toLowerCase() === "core"
                        ? styles.importanceBadgeCore
                        : null,
                    ]}
                  >
                    <Text
                      style={[
                        styles.importanceBadgeText,
                        c.importance.toLowerCase() === "core"
                          ? styles.importanceBadgeTextCore
                          : null,
                      ]}
                    >
                      {c.importance.toUpperCase()}
                    </Text>
                  </View>
                ) : null}
              </View>
              <Text style={styles.conceptExplanation}>{c.explanation}</Text>
            </View>
          ))}
        </Section>
      ) : null}
      {keyPoints && keyPoints.length > 0 ? (
        <Section title="Key points">
          <Bullets items={keyPoints} />
        </Section>
      ) : null}
      {actionItems && actionItems.length > 0 ? (
        <Section title="Action items">
          <Bullets items={actionItems} variant="check" />
        </Section>
      ) : null}
      {glossary && glossary.length > 0 ? (
        <Section title="Glossary">
          {glossary.map((g, i) => (
            <View key={`glossary-${i}`} style={styles.glossaryRow}>
              <Text style={styles.glossaryTerm}>{g.term}</Text>
              <Text style={styles.glossaryDefinition}>{g.definition}</Text>
            </View>
          ))}
        </Section>
      ) : null}
    </View>
  );
}

// --- Flashcards (revealable) ---

interface Flashcard {
  question: string;
  answer: string;
}

function FlashcardsBody({ content }: { content: Record<string, unknown> }) {
  const cards = pickFlashcardArray(content);
  if (!cards || cards.length === 0) {
    return (
      <Section>
        <Text style={styles.emptyText}>No flashcards in this artifact.</Text>
      </Section>
    );
  }

  return (
    <Section
      title={`${cards.length} ${cards.length === 1 ? "card" : "cards"}`}
    >
      {cards.map((card, i) => (
        <FlashcardCard key={`card-${i}`} index={i + 1} card={card} />
      ))}
    </Section>
  );
}

function FlashcardCard({
  index,
  card,
}: {
  index: number;
  card: Flashcard;
}) {
  const [revealed, setRevealed] = useState(false);
  return (
    <Pressable
      style={({ pressed }) => [
        styles.flashcard,
        pressed && styles.flashcardPressed,
      ]}
      onPress={() => setRevealed((v) => !v)}
      accessibilityRole="button"
      accessibilityLabel={
        revealed ? "Hide answer" : "Tap to reveal the answer"
      }
    >
      <View style={styles.flashcardIndexRow}>
        <Text style={styles.flashcardIndex}>{`#${index}`}</Text>
        <Ionicons
          name={revealed ? "eye-off-outline" : "eye-outline"}
          size={16}
          color={Colors.textMuted}
        />
      </View>
      <Text style={styles.flashcardLabel}>QUESTION</Text>
      <Text style={styles.flashcardQuestion}>{card.question}</Text>
      <View style={styles.flashcardDivider} />
      <Text style={styles.flashcardLabel}>ANSWER</Text>
      {revealed ? (
        <Text style={styles.flashcardAnswer}>{card.answer}</Text>
      ) : (
        <Text style={styles.flashcardHint}>Tap to reveal</Text>
      )}
    </Pressable>
  );
}

// --- Quiz ---

interface QuizQuestion {
  question: string;
  options: { label: string; text: string }[];
  correct_answer: string;
  explanation: string;
}

function QuizBody({
  content,
  onQuestionChange,
}: {
  content: Record<string, unknown>;
  onQuestionChange: () => void;
}) {
  const questions = pickQuizQuestions(content);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);

  if (!questions || questions.length === 0) {
    return (
      <Section>
        <Text style={styles.emptyText}>No questions in this artifact.</Text>
      </Section>
    );
  }

  const currentQuestion = questions[currentIndex];
  const answered = picked !== null;
  const isLastQuestion = currentIndex === questions.length - 1;
  const progressWidth = `${((currentIndex + 1) / questions.length) * 100}%` as const;

  const handleContinue = () => {
    if (isLastQuestion) {
      setCompleted(true);
      return;
    }
    setCurrentIndex((index) => index + 1);
    setPicked(null);
    onQuestionChange();
  };

  return (
    <View style={styles.quizBody}>
      <View style={styles.quizProgressHeader}>
        <Text style={styles.quizProgressLabel}>
          {`Question ${currentIndex + 1} / ${questions.length}`}
        </Text>
      </View>
      <View
        style={styles.quizProgressTrack}
        accessibilityRole="progressbar"
        accessibilityLabel="Quiz progress"
        accessibilityValue={{
          min: 1,
          max: questions.length,
          now: currentIndex + 1,
          text: `Question ${currentIndex + 1} of ${questions.length}`,
        }}
        testID="quiz-progress"
      >
        <View style={[styles.quizProgressFill, { width: progressWidth }]} />
      </View>

      <QuizQuestionCard
        key={`q-${currentIndex}`}
        question={currentQuestion}
        picked={picked}
        onPick={setPicked}
      />

      {answered && !completed ? (
        <Pressable
          style={({ pressed }) => [
            styles.quizContinueButton,
            pressed && styles.quizContinueButtonPressed,
          ]}
          onPress={handleContinue}
          accessibilityRole="button"
          accessibilityLabel={isLastQuestion ? "Done" : "Continue"}
          testID="quiz-continue-button"
        >
          <Text style={styles.quizContinueButtonText}>
            {isLastQuestion ? "Done" : "Continue"}
          </Text>
          {!isLastQuestion ? (
            <Ionicons
              name="arrow-forward"
              size={Typography.headline.fontSize}
              color={Colors.onPrimary}
            />
          ) : null}
        </Pressable>
      ) : null}

      {completed ? (
        <View
          style={styles.quizComplete}
          accessibilityRole="text"
          accessibilityLiveRegion="polite"
          testID="quiz-complete"
        >
          <Ionicons
            name="checkmark-circle"
            size={Typography.headline.fontSize}
            color={Colors.onPrimary}
          />
          <Text style={styles.quizCompleteText}>Quiz complete</Text>
        </View>
      ) : null}
    </View>
  );
}

function QuizQuestionCard({
  question,
  picked,
  onPick,
}: {
  question: QuizQuestion;
  picked: string | null;
  onPick: (label: string) => void;
}) {
  const correct = question.correct_answer;
  const answered = picked !== null;

  return (
    <View style={styles.quizCard}>
      <Text style={styles.quizQuestion}>{question.question}</Text>
      <View style={styles.quizOptions}>
        {question.options.map((opt) => {
          const isPicked = picked === opt.label;
          const isCorrect = opt.label.toUpperCase() === correct;
          const showCorrect = answered && isCorrect;
          const showWrong = answered && isPicked && !isCorrect;
          const answerState = showCorrect
            ? ", correct answer"
            : showWrong
              ? ", selected answer, incorrect"
              : "";
          return (
            <Pressable
              key={opt.label}
              style={[
                styles.quizOption,
                showCorrect && styles.quizOptionCorrect,
                showWrong && styles.quizOptionWrong,
              ]}
              onPress={() => !answered && onPick(opt.label)}
              disabled={answered}
              accessibilityRole="button"
              accessibilityLabel={`Option ${opt.label}: ${opt.text}${answerState}`}
              accessibilityState={{ disabled: answered, selected: isPicked }}
              testID={`quiz-option-${opt.label}`}
            >
              <View
                style={[
                  styles.quizOptionLabel,
                  showCorrect && styles.quizOptionLabelCorrect,
                  showWrong && styles.quizOptionLabelWrong,
                ]}
              >
                <Text
                  style={[
                    styles.quizOptionLabelText,
                    showCorrect && styles.quizOptionLabelTextOnAccent,
                    showWrong && styles.quizOptionLabelTextOnAccent,
                  ]}
                >
                  {opt.label}
                </Text>
              </View>
              <Text style={styles.quizOptionText}>{opt.text}</Text>
              {showCorrect ? (
                <Ionicons
                  name="checkmark-circle"
                  size={18}
                  color={Colors.onPrimary}
                />
              ) : null}
              {showWrong ? (
                <Ionicons name="close-circle" size={18} color={Colors.error} />
              ) : null}
            </Pressable>
          );
        })}
      </View>
      {answered ? (
        <View style={styles.quizExplanation}>
          <Text style={styles.quizExplanationLabel}>EXPLANATION</Text>
          <Text style={styles.quizExplanationText}>{question.explanation}</Text>
        </View>
      ) : null}
    </View>
  );
}

// --- Building blocks ---

function Section({
  title,
  children,
}: {
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.section}>
      {title ? <Text style={styles.sectionTitle}>{title}</Text> : null}
      {children}
    </View>
  );
}

function Bullets({
  items,
  variant = "dot",
}: {
  items: string[];
  variant?: "dot" | "check";
}) {
  return (
    <View>
      {items.map((item, i) => (
        <View key={`bullet-${i}`} style={styles.bulletRow}>
          {variant === "check" ? (
            <Ionicons
              name="checkmark-circle"
              size={18}
              color={Colors.primary}
              style={styles.bulletCheck}
            />
          ) : (
            <View style={styles.bulletDot} />
          )}
          <Text style={styles.bulletText}>{item}</Text>
        </View>
      ))}
    </View>
  );
}

// --- Helpers ---

function normalizeArtifactKind(raw: string): ArtifactKind {
  const lower = (raw ?? "").toLowerCase();
  if (lower === "summary_short") return "summary_short";
  if (lower === "summary_detailed") return "summary_detailed";
  if (lower === "summary") return "summary";
  if (lower === "notes") return "notes";
  if (lower === "flashcards") return "flashcards";
  return "quiz";
}

function pickSourceTitle(payload: ArtifactPayload | undefined): string | null {
  const source = payload?.source;
  if (!source || typeof source !== "object") return null;
  const ep = (source as Record<string, unknown>)["episode_title"];
  if (typeof ep === "string" && ep.trim()) return ep.trim();
  const pod = (source as Record<string, unknown>)["podcast_title"];
  if (typeof pod === "string" && pod.trim()) return pod.trim();
  return null;
}

function pickTranslationInfo(
  payload: ArtifactPayload | undefined,
): TranslationInfo | null {
  const translation = payload?.translation;
  if (!translation || typeof translation !== "object") return null;
  const t = translation as Record<string, unknown>;
  const isTranslated = t["is_translated"] === true;
  const translationFailed = t["translation_failed"] === true;
  // Nothing to show when the transcript was already in the target language and
  // no translation failure occurred.
  if (!isTranslated && !translationFailed) return null;
  const translatedFrom =
    typeof t["translated_from"] === "string" && t["translated_from"]
      ? (t["translated_from"] as string)
      : typeof t["detected_language"] === "string"
        ? (t["detected_language"] as string)
        : null;
  const targetLanguage =
    typeof t["target_language"] === "string" ? (t["target_language"] as string) : null;
  return { isTranslated, translatedFrom, targetLanguage, translationFailed };
}

function pickString(obj: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const v = obj[key];
    if (typeof v === "string" && v.trim().length > 0) return v.trim();
  }
  return null;
}

function pickStringArray(
  obj: Record<string, unknown>,
  keys: string[],
): string[] | null {
  for (const key of keys) {
    const v = obj[key];
    if (Array.isArray(v)) {
      const strs = v
        .map((item) => (typeof item === "string" ? item.trim() : ""))
        .filter((s) => s.length > 0);
      if (strs.length > 0) return strs;
    }
  }
  return null;
}

interface ArtifactQuote {
  text: string;
  sourceRef?: string;
}

function pickQuotes(
  obj: Record<string, unknown>,
  keys: string[],
): ArtifactQuote[] | null {
  for (const key of keys) {
    const value = obj[key];
    if (!Array.isArray(value)) continue;
    const quotes: ArtifactQuote[] = [];
    for (const item of value) {
      if (item && typeof item === "object" && !Array.isArray(item)) {
        const record = item as Record<string, unknown>;
        const text = typeof record.text === "string" ? record.text.trim() : "";
        if (!text) continue;
        const sourceRef =
          typeof record.source_ref === "string"
            ? record.source_ref.trim() || undefined
            : undefined;
        quotes.push({ text, sourceRef });
      }
    }
    if (quotes.length > 0) return quotes;
  }
  return null;
}

interface Concept {
  term: string;
  explanation: string;
  importance?: string;
}

function pickConceptArray(obj: Record<string, unknown>): Concept[] | null {
  const v = obj["concepts"];
  if (!Array.isArray(v)) return null;
  const out: Concept[] = [];
  for (const item of v) {
    if (item && typeof item === "object") {
      const r = item as Record<string, unknown>;
      const term = r["term"];
      const explanation = r["explanation"];
      const importance = r["importance"];
      if (typeof term === "string" && typeof explanation === "string") {
        out.push({
          term: term.trim(),
          explanation: explanation.trim(),
          importance:
            typeof importance === "string" ? importance.trim() : undefined,
        });
      }
    }
  }
  return out.length > 0 ? out : null;
}

interface GlossaryEntry {
  term: string;
  definition: string;
}

function pickGlossaryArray(
  obj: Record<string, unknown>,
): GlossaryEntry[] | null {
  const v = obj["glossary"];
  if (!Array.isArray(v)) return null;
  const out: GlossaryEntry[] = [];
  for (const item of v) {
    if (item && typeof item === "object") {
      const r = item as Record<string, unknown>;
      const term = r["term"];
      const definition = r["definition"];
      if (typeof term === "string" && typeof definition === "string") {
        out.push({ term: term.trim(), definition: definition.trim() });
      }
    }
  }
  return out.length > 0 ? out : null;
}

function pickFlashcardArray(
  obj: Record<string, unknown>,
): Flashcard[] | null {
  const v = obj["cards"];
  if (!Array.isArray(v)) return null;
  const out: Flashcard[] = [];
  for (const item of v) {
    if (!item || typeof item !== "object") continue;
    const r = item as Record<string, unknown>;
    const question = r["question"];
    const answer = r["answer"];
    if (typeof question === "string" && typeof answer === "string") {
      out.push({ question: question.trim(), answer: answer.trim() });
    }
  }
  return out.length > 0 ? out : null;
}

function pickQuizQuestions(
  obj: Record<string, unknown>,
): QuizQuestion[] | null {
  const v = obj["questions"];
  if (!Array.isArray(v)) return null;
  const out: QuizQuestion[] = [];
  for (const item of v) {
    if (!item || typeof item !== "object") continue;
    const r = item as Record<string, unknown>;
    const question = r["question"];
    const optionsRaw = r["options"];
    const correct = r["correct_answer"];
    const explanation = r["explanation"];
    if (
      typeof question !== "string" ||
      !Array.isArray(optionsRaw) ||
      typeof correct !== "string" ||
      typeof explanation !== "string"
    ) {
      continue;
    }
    const options: { label: string; text: string }[] = [];
    for (const opt of optionsRaw) {
      if (!opt || typeof opt !== "object") continue;
      const or = opt as Record<string, unknown>;
      const label = or["label"];
      const text = or["text"];
      if (typeof label === "string" && typeof text === "string") {
        options.push({ label: label.trim(), text: text.trim() });
      }
    }
    if (options.length === 0) continue;
    out.push({
      question: question.trim(),
      options,
      correct_answer: correct.trim().toUpperCase(),
      explanation: explanation.trim(),
    });
  }
  return out.length > 0 ? out : null;
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    minHeight: TouchTarget.comfortable,
  },
  headerButton: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.full,
    justifyContent: "center",
    alignItems: "center",
  },
  headerSpacer: {
    width: 44,
    height: 44,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xxl,
  },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
  },

  heroSection: {
    marginBottom: Spacing.lg,
    gap: Spacing.sm,
  },
  kindChip: {
    flexDirection: "row",
    alignSelf: "flex-start",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
  },
  kindChipText: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
    letterSpacing: 0.5,
  },
  heroTitle: {
    fontSize: Typography.display.fontSize,
    fontWeight: Typography.display.fontWeight,
    color: Colors.textMain,
    letterSpacing: Typography.display.letterSpacing,
    lineHeight: 38,
  },
  translationBadge: {
    flexDirection: "row",
    alignSelf: "flex-start",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
  },
  translationBadgeFailed: {
    backgroundColor: Colors.errorContainer,
  },
  translationBadgeText: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
  },
  translationBadgeTextFailed: {
    color: Colors.error,
  },

  section: {
    marginBottom: Spacing.lg,
  },
  sectionTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    marginBottom: Spacing.md,
  },
  body: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    lineHeight: 24,
  },
  emptyText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
  },

  // Summary (short)
  summaryHeadline: {
    fontSize: 24,
    fontWeight: "700",
    color: Colors.textMain,
    lineHeight: 32,
    marginBottom: Spacing.lg,
  },
  takeawayCard: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: Spacing.sm + 4,
    backgroundColor: Colors.primary,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md + 2,
    ...Shadows.soft,
  },
  takeawayIcon: {
    marginTop: 2,
  },
  takeawayText: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
    color: Colors.onPrimary,
    lineHeight: 24,
  },

  // Summary (detailed)
  topicChipsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: Spacing.sm,
  },
  topicChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
  },
  topicChipText: {
    fontSize: Typography.small.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  quoteCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md + 2,
    marginBottom: Spacing.sm + 4,
    borderLeftWidth: 4,
    borderLeftColor: Colors.primary,
    ...Shadows.soft,
  },
  quoteMark: {
    fontSize: 32,
    lineHeight: 32,
    color: Colors.primary,
    fontWeight: "800",
    marginBottom: Spacing.xs,
  },
  quoteSourceRef: {
    marginTop: Spacing.xs,
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMuted,
  },
  quoteText: {
    fontSize: Typography.body.fontSize,
    fontStyle: "italic",
    color: Colors.textMain,
    lineHeight: 24,
  },

  // Bullets
  bulletRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: Spacing.sm + 2,
    gap: Spacing.sm + 2,
  },
  bulletDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.primary,
    marginTop: 9,
  },
  bulletCheck: {
    marginTop: 2,
  },
  bulletText: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    lineHeight: 24,
  },

  // Notes — concepts & glossary
  conceptCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    marginBottom: Spacing.sm + 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
    ...Shadows.soft,
  },
  conceptHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: Spacing.xs + 2,
    gap: Spacing.sm,
  },
  conceptTerm: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
  },
  conceptExplanation: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    lineHeight: 23,
  },
  importanceBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surfaceContainerHigh,
  },
  importanceBadgeCore: {
    backgroundColor: Colors.primary,
  },
  importanceBadgeText: {
    fontSize: 10,
    fontWeight: "800",
    color: Colors.textMuted,
    letterSpacing: 0.6,
  },
  importanceBadgeTextCore: {
    color: Colors.onPrimary,
  },
  glossaryRow: {
    paddingVertical: Spacing.sm + 2,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.outlineVariant,
  },
  glossaryTerm: {
    fontSize: Typography.body.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    marginBottom: 2,
  },
  glossaryDefinition: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    lineHeight: 23,
  },

  // Flashcards
  flashcard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    marginBottom: Spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
    ...Shadows.soft,
  },
  flashcardPressed: {
    transform: [{ scale: 0.99 }],
  },
  flashcardIndexRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: Spacing.sm,
  },
  flashcardIndex: {
    fontSize: Typography.small.fontSize,
    fontWeight: "700",
    color: Colors.textMuted,
    letterSpacing: 0.5,
  },
  flashcardLabel: {
    fontSize: 11,
    fontWeight: "800",
    color: Colors.textMuted,
    letterSpacing: 0.8,
    marginBottom: Spacing.xs,
  },
  flashcardQuestion: {
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
    lineHeight: 24,
  },
  flashcardAnswer: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    lineHeight: 24,
  },
  flashcardHint: {
    fontSize: Typography.body.fontSize,
    fontStyle: "italic",
    color: Colors.textMuted,
  },
  flashcardDivider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: Colors.outlineVariant,
    marginVertical: Spacing.md,
  },

  // Quiz
  quizBody: {
    marginBottom: Spacing.lg,
  },
  quizProgressHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: Spacing.sm,
  },
  quizProgressLabel: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
  },
  quizProgressTrack: {
    height: Spacing.xs,
    overflow: "hidden",
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    marginBottom: Spacing.lg,
  },
  quizProgressFill: {
    height: "100%",
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary,
  },
  quizCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    marginBottom: Spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
    ...Shadows.soft,
  },
  quizQuestion: {
    fontSize: Typography.body.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    lineHeight: 24,
    marginBottom: Spacing.md,
  },
  quizOptions: {
    gap: Spacing.sm,
  },
  quizOption: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm + 4,
    paddingVertical: Spacing.sm + 4,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainerLow,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
    minHeight: TouchTarget.minimum,
  },
  quizOptionCorrect: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  quizOptionWrong: {
    backgroundColor: Colors.errorContainer,
    borderColor: Colors.errorContainer,
  },
  quizOptionLabel: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.surface,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
  },
  quizOptionLabelCorrect: {
    backgroundColor: Colors.onPrimary,
    borderColor: Colors.onPrimary,
  },
  quizOptionLabelWrong: {
    backgroundColor: Colors.error,
    borderColor: Colors.error,
  },
  quizOptionLabelText: {
    fontSize: 13,
    fontWeight: "800",
    color: Colors.textMain,
  },
  quizOptionLabelTextOnAccent: {
    color: Colors.surface,
  },
  quizOptionText: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    lineHeight: 22,
  },
  quizExplanation: {
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.outlineVariant,
  },
  quizExplanationLabel: {
    fontSize: 11,
    fontWeight: "800",
    color: Colors.textMuted,
    letterSpacing: 0.8,
    marginBottom: Spacing.xs,
  },
  quizExplanationText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    lineHeight: 23,
  },
  quizContinueButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
    minHeight: TouchTarget.comfortable,
    paddingHorizontal: Spacing.lg,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary,
  },
  quizContinueButtonPressed: {
    opacity: 0.8,
  },
  quizContinueButtonText: {
    fontSize: Typography.body.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.onPrimary,
  },
  quizComplete: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
    minHeight: TouchTarget.comfortable,
    paddingHorizontal: Spacing.lg,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary,
  },
  quizCompleteText: {
    fontSize: Typography.body.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.onPrimary,
  },

  // Failure / not-ready states
  failedIcon: {
    marginBottom: Spacing.md,
  },
  failedTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
    marginBottom: Spacing.xs,
  },
  failedMessage: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    lineHeight: 24,
    marginBottom: Spacing.lg,
  },
  refreshButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm + 4,
    borderRadius: BorderRadius.lg,
    minHeight: TouchTarget.minimum,
  },
  refreshButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.onPrimary,
  },
});
