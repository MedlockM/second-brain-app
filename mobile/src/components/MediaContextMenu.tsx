/**
 * What a long press on a media vignette opens: a context menu anchored to the
 * row that was pressed, on the shape of the iOS Files menu.
 *
 * The row is measured with `measureInWindow` at long-press time and the rect is
 * handed here, which is what makes the menu *anchored* rather than pinned to the
 * bottom edge: the card is placed just under the vignette, or just above it when
 * the vignette sits too low for the card to fit underneath. A copy of the row is
 * redrawn at that rect, slightly enlarged, above the blurred backdrop — so the
 * pressed item and the menu are the only sharp things on screen and the gesture
 * visibly names its target.
 *
 * Rebuilt in JS on purpose (task-346). A system `UIMenu` cannot be styled and
 * this look is required on Android too, which is the project's shipping path;
 * and `package.json` carries neither `react-native-reanimated` nor
 * `react-native-gesture-handler`, which a context-menu library would drag in.
 * Nothing here needs them: the animation is one scale-and-fade with no
 * continuous gesture, which the `Animated` API of React Native core does.
 *
 * The orchestration — which media is targeted, the destructive confirmation, the
 * network calls — belongs to `useMediaActions`; this file is the surface only.
 */

import { useEffect, useMemo, type ReactNode } from "react";
import {
  ActivityIndicator,
  Animated,
  Easing,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { BlurView } from "expo-blur";
import { Ionicons } from "@expo/vector-icons";
import {
  BorderRadius,
  Colors,
  Shadows,
  Spacing,
  TouchTarget,
  Typography,
} from "../constants/theme";
import { t } from "../i18n";
import type { MediaListItem } from "../types/media";

/**
 * Window-space rectangle of the pressed row, straight out of
 * `measureInWindow`. The menu is placed against it and the lifted copy of the
 * row is drawn on it, so both come from one measurement.
 */
export interface AnchorRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface MediaContextMenuProps {
  visible: boolean;
  /** The media the long press landed on; `null` before any press. */
  item: MediaListItem | null;
  /** Where that row sits on screen, measured when the press was recognised. */
  anchor: AnchorRect | null;
  /**
   * Redraws the pressed row for the copy lifted above the blur.
   *
   * The surface supplies it because only it knows what its rows look like — the
   * library list and the sources list of a collection do not share a component.
   * The redrawn row must carry no outer margin: it is laid out on the measured
   * rect, and `measureInWindow` reports a box margins are already outside of.
   */
  renderPreview: (item: MediaListItem) => ReactNode;
  /** A deletion is in flight: the rows are inert and Delete shows a spinner. */
  isDeleting: boolean;
  /**
   * The menu has finished dismissing and `visible` can go false.
   *
   * Called after the exit animation, not when the dismissal is asked for: the
   * menu needs to stay mounted while it fades.
   */
  onClose: () => void;
  onMove: () => void;
  onRename: () => void;
  onDelete: () => void;
}

/** Wide enough for the longest label in any catalogue, narrow like the iOS one. */
const MENU_WIDTH = 240;
const ROW_HEIGHT = TouchTarget.minimum;
const CARD_PADDING_VERTICAL = Spacing.xs;

/**
 * Known before layout, and exactly — every row is a fixed `ROW_HEIGHT` and the
 * card has no other content. The up/down decision has to be made in the same
 * frame the menu appears, so measuring the card first (and flipping it after)
 * would show the menu in the wrong place for one frame.
 */
const MENU_HEIGHT =
  ROW_HEIGHT * 3 + CARD_PADDING_VERTICAL * 2 + StyleSheet.hairlineWidth;

/** Breathing room between the lifted vignette and the card. */
const MENU_GAP = Spacing.sm;
/** Smallest distance the card keeps from any screen edge. */
const SCREEN_EDGE = Spacing.md;
/** How much the pressed row grows as it lifts. Enough to read, not a jump. */
const PREVIEW_SCALE = 1.04;

const OPEN_DURATION = 160;
const CLOSE_DURATION = 120;

export function MediaContextMenu({
  visible,
  item,
  anchor,
  renderPreview,
  isDeleting,
  onClose,
  onMove,
  onRename,
  onDelete,
}: MediaContextMenuProps): React.JSX.Element | null {
  const insets = useSafeAreaInsets();
  const { width: screenWidth, height: screenHeight } = useWindowDimensions();

  // One value drives the whole appearance: the backdrop opacity, the lift of the
  // vignette and the scale of the card. Not a ref — it is created once and read
  // during render, which is what `useMemo` is for.
  const progress = useMemo(() => new Animated.Value(0), []);

  // Reset before playing: a menu closed by its own exit ends at 0, but one the
  // caller closed outright (a deletion just went through) is left at 1.
  useEffect(() => {
    if (!visible) return;
    progress.setValue(0);
    Animated.timing(progress, {
      toValue: 1,
      duration: OPEN_DURATION,
      easing: Easing.out(Easing.quad),
      useNativeDriver: true,
    }).start();
  }, [visible, progress]);

  if (!visible || !item || !anchor) return null;

  // Downwards whenever the card fits under the vignette, upwards otherwise: a
  // row near the end of a list must not push the menu off screen.
  const roomBelow = screenHeight - insets.bottom - SCREEN_EDGE;
  const opensDown = anchor.y + anchor.height + MENU_GAP + MENU_HEIGHT <= roomBelow;
  const preferredTop = opensDown
    ? anchor.y + anchor.height + MENU_GAP
    : anchor.y - MENU_GAP - MENU_HEIGHT;
  const top = clamp(
    preferredTop,
    insets.top + SCREEN_EDGE,
    Math.max(insets.top + SCREEN_EDGE, roomBelow - MENU_HEIGHT),
  );
  // Left-aligned on the vignette, like the Files menu, then held inside the
  // gutters so a row that starts near the right edge does not push it out.
  const left = clamp(anchor.x, SCREEN_EDGE, screenWidth - SCREEN_EDGE - MENU_WIDTH);

  const previewScale = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [1, PREVIEW_SCALE],
  });
  const cardScale = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [0.92, 1],
  });

  /**
   * Plays the exit, then hands control back to the caller.
   *
   * The caller keeps `visible` true for the length of the animation — it only
   * learns about the dismissal through `onClose`, once the menu has faded — which
   * is what makes the fade-out possible without a second piece of state tracking
   * whether the modal is still on screen.
   *
   * Move and Rename both open something else (the collection picker is pushed on
   * the navigator, the rename dialog is another modal) and a modal still up sits
   * over whatever appears underneath it. So the action waits one frame past the
   * close, by which time the unmount has been committed. One code path on both
   * platforms, unlike waiting on iOS's `onDismiss`, which Android never fires.
   */
  const requestClose = (action?: () => void) => {
    // A deletion in flight owns the menu: hiding it would strand the spinner and
    // leave the user unsure whether the call went out.
    if (isDeleting) return;
    Animated.timing(progress, {
      toValue: 0,
      duration: CLOSE_DURATION,
      easing: Easing.in(Easing.quad),
      useNativeDriver: true,
    }).start(({ finished }) => {
      if (!finished) return;
      onClose();
      if (action) requestAnimationFrame(action);
    });
  };

  return (
    <Modal
      visible
      transparent
      // The appearance is animated here, anchored to the vignette; the platform
      // transitions would slide or fade the whole screen instead.
      animationType="none"
      statusBarTranslucent
      onRequestClose={() => requestClose()}
    >
      <View style={styles.root}>
        <Animated.View
          style={[StyleSheet.absoluteFill, { opacity: progress }]}
          pointerEvents="none"
        >
          <BlurView
            intensity={40}
            tint="light"
            experimentalBlurMethod="dimezisBlurView"
            style={StyleSheet.absoluteFill}
          />
          {/* The dim over the blur. The design system has no scrim token, so
              this is textMain at 35% — the only literal colour in this file,
              and the same value the add-source sheet uses. It also guarantees
              the backdrop reads as inert on an Android device whose blur
              support degrades. */}
          <View style={styles.scrim} />
        </Animated.View>

        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={() => requestClose()}
          accessibilityLabel={t("common.dismiss")}
          accessibilityRole="button"
          testID="media-actions-backdrop"
        />

        {/* The pressed row, redrawn on its own rect and lifted. Inert: a tap on
            it is a tap on the backdrop, which is what dismisses the menu. */}
        <Animated.View
          pointerEvents="none"
          style={[
            styles.preview,
            {
              left: anchor.x,
              top: anchor.y,
              width: anchor.width,
              height: anchor.height,
              transform: [{ scale: previewScale }],
            },
          ]}
        >
          {renderPreview(item)}
        </Animated.View>

        <Animated.View
          style={[
            styles.cardWrapper,
            {
              top,
              left,
              opacity: progress,
              transform: [{ scale: cardScale }],
              transformOrigin: opensDown ? "top left" : "bottom left",
            },
          ]}
          testID="media-actions-menu"
        >
          <BlurView
            intensity={80}
            tint="light"
            experimentalBlurMethod="dimezisBlurView"
            style={styles.card}
          >
            {/* Translucency without a new colour token: the surface white is
                laid over the blur at partial opacity, so what is behind the
                card still shows through the way platform vibrancy does. */}
            <View style={styles.cardVeil} pointerEvents="none" />

            <MenuRow
              icon="folder-outline"
              label={t("mediaActions.move.label")}
              onPress={() => requestClose(onMove)}
              disabled={isDeleting}
              testID="media-actions-move"
            />
            <MenuRow
              icon="pencil-outline"
              label={t("mediaActions.rename.label")}
              onPress={() => requestClose(onRename)}
              disabled={isDeleting}
              testID="media-actions-rename"
            />
            {/* The one line in the card, and the only thing separating the
                destructive action from the reversible ones. */}
            <View style={styles.divider} />
            <MenuRow
              icon="trash-outline"
              label={t("mediaActions.delete.label")}
              onPress={onDelete}
              disabled={isDeleting}
              isBusy={isDeleting}
              destructive
              testID="media-actions-delete"
            />
          </BlurView>
        </Animated.View>
      </View>
    </Modal>
  );
}

/**
 * One line of the menu: a glyph, a label, nothing else.
 *
 * No description, no circled icon, no chevron — none of the three actions opens
 * a submenu, and the compactness is what makes this read as a context menu
 * rather than a sheet.
 */
function MenuRow({
  icon,
  label,
  onPress,
  disabled,
  isBusy = false,
  destructive = false,
  testID,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
  disabled: boolean;
  isBusy?: boolean;
  destructive?: boolean;
  testID: string;
}) {
  const tint = destructive ? Colors.error : Colors.textMain;

  return (
    <Pressable
      style={({ pressed }) => [
        styles.row,
        pressed && styles.rowPressed,
        disabled && styles.rowDisabled,
      ]}
      onPress={onPress}
      disabled={disabled}
      testID={testID}
      accessibilityLabel={label}
      accessibilityRole="button"
      accessibilityState={{ disabled }}
    >
      {isBusy ? (
        <ActivityIndicator size="small" color={tint} style={styles.rowGlyph} />
      ) : (
        <Ionicons name={icon} size={20} color={tint} style={styles.rowGlyph} />
      )}
      <Text style={[styles.rowLabel, { color: tint }]} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  scrim: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(43, 45, 66, 0.35)",
  },
  preview: {
    position: "absolute",
  },
  cardWrapper: {
    position: "absolute",
    width: MENU_WIDTH,
    borderRadius: BorderRadius.xl,
    // On the wrapper rather than the card: a shadow does not survive the
    // `overflow: hidden` the rounded blur needs.
    ...Shadows.soft,
  },
  card: {
    borderRadius: BorderRadius.xl,
    paddingVertical: CARD_PADDING_VERTICAL,
    overflow: "hidden",
  },
  cardVeil: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: Colors.surface,
    opacity: 0.78,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    height: ROW_HEIGHT,
    paddingHorizontal: Spacing.md,
  },
  rowPressed: {
    backgroundColor: Colors.surfaceContainerHigh,
  },
  rowDisabled: {
    opacity: 0.5,
  },
  // Fixed width so the labels align whether the glyph is an icon or a spinner.
  rowGlyph: {
    width: Spacing.lg,
    textAlign: "center",
  },
  rowLabel: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    fontWeight: Typography.label.fontWeight,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: Colors.outlineVariant,
  },
});
