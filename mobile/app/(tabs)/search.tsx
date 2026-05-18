import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  FlatList,
  ActivityIndicator,
  Pressable,
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useAuth } from "../../src/contexts/AuthContext";
import { useDebounce } from "../../src/hooks/useDebounce";
import {
  SearchService,
  SearchFilters,
} from "../../src/services/searchService";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../../src/constants/theme";
import type {
  MediaItemContract,
  MediaType,
  MediaItemStatus,
  SourcePlatform,
} from "../../src/types/media";

// --- Filter chip definitions ---

interface FilterChipDef {
  label: string;
  type: MediaType | null; // null = "All"
}

const TYPE_FILTERS: FilterChipDef[] = [
  { label: "All", type: null },
  { label: "Podcasts", type: "podcast_episode" },
  { label: "Articles", type: "article" },
  { label: "YouTube", type: "youtube_video" },
  { label: "Videos", type: "short_video" },
  { label: "Audio", type: "audio_file" },
];

// --- Helper functions ---

function getMediaTypeIcon(
  type: MediaType,
): keyof typeof Ionicons.glyphMap {
  switch (type) {
    case "podcast_episode":
      return "mic-outline";
    case "article":
      return "document-text-outline";
    case "youtube_video":
      return "logo-youtube";
    case "short_video":
      return "videocam-outline";
    case "audio_file":
      return "musical-notes-outline";
    case "shared_text":
      return "chatbox-outline";
    default:
      return "link-outline";
  }
}

function getSourceLabel(platform: SourcePlatform): string {
  switch (platform) {
    case "spotify":
      return "Spotify";
    case "apple_podcasts":
      return "Apple Podcasts";
    case "deezer":
      return "Deezer";
    case "rss":
      return "RSS";
    case "podcast_index":
      return "Podcast Index";
    case "youtube":
      return "YouTube";
    case "instagram":
      return "Instagram";
    case "tiktok":
      return "TikTok";
    case "x":
      return "X";
    case "whatsapp":
      return "WhatsApp";
    case "web":
      return "Web";
    case "direct_url":
      return "Direct URL";
    default:
      return "Unknown";
  }
}

function getStatusLabel(status: MediaItemStatus): string {
  switch (status) {
    case "ingested":
      return "Ingested";
    case "resolving":
      return "Resolving";
    case "processing":
      return "Processing";
    case "ready_for_artifacts":
      return "Ready";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return status;
  }
}

function getStatusColor(status: MediaItemStatus): string {
  switch (status) {
    case "ready_for_artifacts":
      return "#e8f5e9";
    case "failed":
    case "cancelled":
      return Colors.errorContainer;
    default:
      return Colors.surfaceContainerHigh;
  }
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function getDisplayTitle(item: MediaItemContract): string {
  // Use the URL as title since MediaItemContract does not have a title field.
  // The search endpoint may augment results with a title in the future.
  try {
    const url = new URL(item.original_url);
    // Show domain + path for readability
    const path = url.pathname === "/" ? "" : url.pathname;
    return `${url.hostname.replace(/^www\./, "")}${path}`;
  } catch {
    return item.original_url;
  }
}

// --- Main Screen Component ---

export default function SearchScreen() {
  const { token } = useAuth();
  const router = useRouter();

  // Search state
  const [query, setQuery] = useState("");
  const [activeTypeFilter, setActiveTypeFilter] = useState<MediaType | null>(
    null,
  );
  const [results, setResults] = useState<MediaItemContract[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounce the search query
  const debouncedQuery = useDebounce(query, 300);

  // Execute search when debounced query or filter changes
  useEffect(() => {
    if (!token) return;

    // Only search if there is a query or a filter active
    if (!debouncedQuery.trim() && !activeTypeFilter) {
      setResults([]);
      setTotalResults(0);
      setHasSearched(false);
      setError(null);
      return;
    }

    const performSearch = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const filters: SearchFilters = {};
        if (activeTypeFilter) {
          filters.type = activeTypeFilter;
        }

        const response = await SearchService.searchMedia(
          token,
          debouncedQuery,
          filters,
        );

        setResults(response.items);
        setTotalResults(response.total);
        setHasSearched(true);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Search failed";
        setError(message);
        setResults([]);
        setTotalResults(0);
        setHasSearched(true);
      } finally {
        setIsLoading(false);
      }
    };

    performSearch();
  }, [debouncedQuery, activeTypeFilter, token]);

  const handleClearQuery = useCallback(() => {
    setQuery("");
  }, []);

  const handleFilterPress = useCallback((type: MediaType | null) => {
    setActiveTypeFilter(type);
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      {/* Header with search input */}
      <View style={styles.header}>
        <Text style={styles.title}>Search</Text>

        {/* Search Input */}
        <View style={styles.searchBarContainer}>
          <Ionicons
            name="search"
            size={20}
            color={Colors.textMuted}
            style={styles.searchIcon}
          />
          <TextInput
            style={styles.searchInput}
            placeholder="Search your library..."
            placeholderTextColor={Colors.textMuted}
            value={query}
            onChangeText={setQuery}
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="search"
          />
          {query.length > 0 && (
            <Pressable
              onPress={handleClearQuery}
              style={styles.clearButton}
              hitSlop={8}
            >
              <Ionicons name="close" size={18} color={Colors.textMuted} />
            </Pressable>
          )}
        </View>
      </View>

      {/* Filter Chips */}
      <View style={styles.filtersContainer}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filtersContent}
        >
          {TYPE_FILTERS.map((chip) => (
            <Pressable
              key={chip.label}
              style={[
                styles.filterChip,
                activeTypeFilter === chip.type && styles.filterChipActive,
              ]}
              onPress={() => handleFilterPress(chip.type)}
            >
              <Text
                style={[
                  styles.filterChipText,
                  activeTypeFilter === chip.type &&
                    styles.filterChipTextActive,
                ]}
              >
                {chip.label}
              </Text>
            </Pressable>
          ))}
        </ScrollView>
      </View>

      {/* Results Area */}
      <View style={styles.resultsArea}>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} />
        ) : !hasSearched ? (
          <InitialState />
        ) : results.length === 0 ? (
          <NoResultsState query={debouncedQuery} />
        ) : (
          <FlatList
            data={results}
            keyExtractor={(item) => item.media_item_id}
            renderItem={({ item }) => (
              <ResultCard
                item={item}
                onPress={() => router.push(`/media/${item.media_item_id}`)}
              />
            )}
            contentContainerStyle={styles.resultsList}
            showsVerticalScrollIndicator={false}
            ListHeaderComponent={
              <Text style={styles.resultsCount}>
                {totalResults} {totalResults === 1 ? "result" : "results"} found
              </Text>
            }
            ListFooterComponent={
              results.length > 0 ? (
                <Text style={styles.endOfResults}>End of results</Text>
              ) : null
            }
          />
        )}
      </View>
    </SafeAreaView>
  );
}

// --- Sub-components ---

function InitialState() {
  return (
    <View style={styles.emptyContainer}>
      <Ionicons
        name="search-outline"
        size={48}
        color={Colors.textMuted}
        style={styles.emptyIcon}
      />
      <Text style={styles.emptyTitle}>Search your media library</Text>
      <Text style={styles.emptyHint}>
        Find transcripts, summaries, and notes across all your saved content.
      </Text>
    </View>
  );
}

function NoResultsState({ query }: { query: string }) {
  return (
    <View style={styles.emptyContainer}>
      <Ionicons
        name="document-outline"
        size={48}
        color={Colors.textMuted}
        style={styles.emptyIcon}
      />
      <Text style={styles.emptyTitle}>No results found</Text>
      <Text style={styles.emptyHint}>
        No matches for "{query}". Try different keywords or adjust your filters.
      </Text>
    </View>
  );
}

function LoadingState() {
  return (
    <View style={styles.emptyContainer}>
      <ActivityIndicator size="large" color={Colors.primary} />
      <Text style={[styles.emptyHint, { marginTop: Spacing.md }]}>
        Searching...
      </Text>
    </View>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <View style={styles.emptyContainer}>
      <Ionicons
        name="alert-circle-outline"
        size={48}
        color={Colors.error}
        style={styles.emptyIcon}
      />
      <Text style={styles.emptyTitle}>Something went wrong</Text>
      <Text style={styles.emptyHint}>{message}</Text>
    </View>
  );
}

function ResultCard({ item, onPress }: { item: MediaItemContract; onPress: () => void }) {
  const displayTitle = getDisplayTitle(item);
  const sourceLabel = getSourceLabel(item.source_platform);
  const dateLabel = formatDate(item.created_at);
  const statusLabel = getStatusLabel(item.status);
  const statusColor = getStatusColor(item.status);
  const typeIcon = getMediaTypeIcon(item.media_type);

  return (
    <Pressable
      style={styles.card}
      onPress={onPress}
      accessibilityLabel={`${displayTitle}, ${sourceLabel}`}
      accessibilityRole="button"
    >
      {/* Card Header: source icon + label + date */}
      <View style={styles.cardHeader}>
        <View style={styles.cardSourceRow}>
          <Ionicons name={typeIcon} size={16} color={Colors.primary} />
          <Text style={styles.cardSourceLabel}>{sourceLabel}</Text>
        </View>
        <Text style={styles.cardDate}>{dateLabel}</Text>
      </View>

      {/* Title */}
      <Text style={styles.cardTitle} numberOfLines={2}>
        {displayTitle}
      </Text>

      {/* Footer: status badge */}
      <View style={styles.cardFooter}>
        <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
          <Text style={styles.statusText}>{statusLabel}</Text>
        </View>
      </View>
    </Pressable>
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },

  // Header
  header: {
    backgroundColor: Colors.surface,
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.md,
  },
  title: {
    fontSize: Typography.display.fontSize,
    fontWeight: Typography.display.fontWeight,
    color: Colors.textMain,
    letterSpacing: Typography.display.letterSpacing,
    marginBottom: Spacing.md,
  },

  // Search bar - minimum height meets touch target (AC#2)
  searchBarContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.background,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.outlineVariant,
    height: TouchTarget.minimum,
    paddingHorizontal: Spacing.md,
  },
  searchIcon: {
    marginRight: Spacing.sm,
  },
  searchInput: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    fontWeight: Typography.body.fontWeight,
    color: Colors.textMain,
    height: "100%",
    paddingVertical: 0,
  },
  clearButton: {
    marginLeft: Spacing.sm,
    padding: Spacing.xs,
  },

  // Filter chips
  filtersContainer: {
    backgroundColor: Colors.surface,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.outlineVariant,
    paddingVertical: Spacing.sm + 4,
  },
  filtersContent: {
    paddingHorizontal: Spacing.md,
    gap: Spacing.sm,
  },
  filterChip: {
    height: 40,
    minWidth: TouchTarget.minimum,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.background,
    alignItems: "center",
    justifyContent: "center",
  },
  filterChipActive: {
    backgroundColor: Colors.primary,
  },
  filterChipText: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
  },
  filterChipTextActive: {
    fontWeight: "600",
    color: "#1c1b1a",
  },

  // Results area
  resultsArea: {
    flex: 1,
  },
  resultsList: {
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xxl,
    gap: Spacing.md,
  },
  resultsCount: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: Spacing.sm,
  },
  endOfResults: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    marginTop: Spacing.lg,
  },

  // Empty states
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
  },
  emptyIcon: {
    marginBottom: Spacing.md,
  },
  emptyTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
  },
  emptyHint: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    marginTop: Spacing.sm,
    lineHeight: Typography.body.lineHeight,
  },

  // Result card
  card: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
    ...Shadows.soft,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: Spacing.sm,
  },
  cardSourceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  cardSourceLabel: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  cardDate: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  cardTitle: {
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
    lineHeight: 22,
    marginBottom: Spacing.sm,
  },
  cardFooter: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    marginTop: Spacing.xs,
  },
  statusBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.sm,
  },
  statusText: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
  },
});
