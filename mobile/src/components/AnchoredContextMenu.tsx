/**
 * What a long press on something in Library opens: a context menu anchored to
 * the thing that was pressed, on the shape of the iOS Files menu.
 *
 * The pressed view is measured with `measureInWindow` at long-press time and the
 * rect is handed here, which is what makes the menu *anchored* rather than pinned
 * to the bottom edge: the card is placed just under the view, or just above it
 * when the view sits too low for the card to fit underneath. A copy of the view is
 * redrawn at that rect, slightly enlarged, above the blurred backdrop — so the
 * pressed thing and the menu are the only sharp things on screen and the gesture
 * visibly names its target.
 *
 * One component for every target, and deliberately so: a media row offers Move,
 * Rename and Delete, a collection tile offers Rename and Delete, and a second
 * file re-implementing the backdrop, the lifted preview and the up/down geometry
 * for the second of those is exactly what this generalization avoids. The target
 * is therefore a type parameter and the rows are data — an ordered list of
 * actions, from which the card's height is derived.
 *
 * Rebuilt in JS on purpose (task-346). A system `UIMenu` cannot be styled, and
 * the ready-made shape fails on two counts beyond that. `Link.Menu` and
 * `Link.Preview` do ship inside `expo-router`, but `LinkMenu` is annotated
 * `@platform ios`, so Android — the project's shipping path — would lose the long
 * press entirely; and a `UIMenu` dismisses itself the moment a row is selected,
 * which leaves nowhere for the in-flight spinner on Delete to live. The animation
 * needs no gesture library either: it is one scale-and-fade with no continuous
 * gesture, which the `Animated` API of React Native core does.
 *
 * The orchestration — which thing is targeted, the destructive confirmation, the
 * network calls — belongs to `useMediaActions` / `useCollectionActions`; this file
 * is the surface only.
 */

import { Fragment, useEffect, useMemo, type ReactNode } from "react";
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
import { GlassSurface } from "./GlassSurface";

/**
 * Window-space rectangle of the pressed view, straight out of
 * `measureInWindow`. The menu is placed against it and the lifted copy of the
 * view is drawn on it, so both come from one measurement.
 */
export interface AnchorRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** One line of the menu, as the hook that owns the behaviour declares it. */
export interface ContextMenuAction {
  /** Stable identity of the row, for its React key. */
  key: string;
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
  /**
   * Tinted `Colors.error`, and preceded by the card's one hairline.
   *
   * The divider is derived from this rather than declared a second time: its
   * whole job is to separate the destructive action from the reversible ones, so
   * a menu cannot end up with a line in a place that means nothing.
   */
  destructive?: boolean;
  /** Spinner in place of the glyph: this row's own call is in flight. */
  isBusy?: boolean;
  /**
   * The menu fades out first and the action runs one frame later.
   *
   * What a row that opens something else needs — the collection picker is pushed
   * on the navigator, the rename dialog is another modal — because a modal still
   * up sits over whatever appears underneath it. The destructive row sets this
   * false: it owns the menu while its confirmation and its spinner are on screen.
   */
  closesMenu: boolean;
  testID: string;
}

export interface AnchoredContextMenuProps<T> {
  visible: boolean;
  /** The thing the long press landed on; `null` before any press. */
  target: T | null;
  /** Where that view sits on screen, measured when the press was recognised. */
  anchor: AnchorRect | null;
  /**
   * Redraws the pressed view for the copy lifted above the blur.
   *
   * The surface supplies it because only it knows what its rows and tiles look
   * like — the library list, the collections grid and the sources list of a
   * collection do not share a component. The redrawn view must carry no outer
   * margin: it is laid out on the measured rect, and `measureInWindow` reports a
   * box margins are already outside of.
   */
  renderPreview: (target: T) => ReactNode;
  /** The rows, top to bottom. Two or three today; the card sizes itself. */
  actions: readonly ContextMenuAction[];
  /** A call is in flight: every row is inert until it answers. */
  isBusy: boolean;
  /**
   * The menu has finished dismissing and `visible` can go false.
   *
   * Called after the exit animation, not when the dismissal is asked for: the
   * menu needs to stay mounted while it fades.
   */
  onClose: () => void;
  /** Names the card and its backdrop for a flow, e.g. `media-actions`. */
  testIDPrefix: string;
}

/** Wide enough for the longest label in any catalogue, narrow like the iOS one. */
const MENU_WIDTH = 240;
const ROW_HEIGHT = TouchTarget.minimum;
const CARD_PADDING_VERTICAL = Spacing.xs;

/** Breathing room between the lifted view and the card. */
const MENU_GAP = Spacing.sm;
/** Smallest distance the card keeps from any screen edge. */
const SCREEN_EDGE = Spacing.md;
/** How much the pressed view grows as it lifts. Enough to read, not a jump. */
const PREVIEW_SCALE = 1.04;

/**
 * Where the card's fade starts, and the reason it is not zero.
 *
 * `expo-glass-effect` documents that an `opacity` of `0` on the glass view **or
 * on any of its ancestors** stops the material rendering at all — and
 * `cardWrapper`, whose opacity the entry animation drives, is exactly such an
 * ancestor. A literal `opacity: progress` therefore produced a menu card that
 * came up as a plain untinted view: a failure mode that reads as a styling
 * mistake rather than as a documented constraint, which is why it is named here.
 * Starting the fade a hair above zero keeps the material in the render tree for
 * the whole animation while being invisible on the first frame.
 */
const CARD_MIN_OPACITY = 0.05;

const OPEN_DURATION = 160;
const CLOSE_DURATION = 120;

/**
 * Exactly how tall the card will be, known before it is laid out.
 *
 * Every row is a fixed `ROW_HEIGHT` and the card holds nothing else, so the
 * height is a sum rather than a measurement — which it has to be: the up/down
 * decision is made in the same frame the menu appears, and measuring the card
 * first would show it in the wrong place for one frame.
 */
function measureCard(actions: readonly ContextMenuAction[]): number {
  const dividers = actions.filter(
    (action, index) => action.destructive === true && index > 0,
  ).length;
  return (
    ROW_HEIGHT * actions.length +
    CARD_PADDING_VERTICAL * 2 +
    StyleSheet.hairlineWidth * dividers
  );
}

export function AnchoredContextMenu<T>({
  visible,
  target,
  anchor,
  renderPreview,
  actions,
  isBusy,
  onClose,
  testIDPrefix,
}: AnchoredContextMenuProps<T>): React.JSX.Element | null {
  const insets = useSafeAreaInsets();
  const { width: screenWidth, height: screenHeight } = useWindowDimensions();

  // One value drives the whole appearance: the backdrop opacity, the lift of the
  // pressed view and the scale of the card. Not a ref — it is created once and
  // read during render, which is what `useMemo` is for.
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

  if (!visible || target === null || !anchor) return null;

  const menuHeight = measureCard(actions);

  // Downwards whenever the card fits under the pressed view, upwards otherwise:
  // a row near the end of a list must not push the menu off screen.
  const roomBelow = screenHeight - insets.bottom - SCREEN_EDGE;
  const opensDown = anchor.y + anchor.height + MENU_GAP + menuHeight <= roomBelow;
  const preferredTop = opensDown
    ? anchor.y + anchor.height + MENU_GAP
    : anchor.y - MENU_GAP - menuHeight;
  const top = clamp(
    preferredTop,
    insets.top + SCREEN_EDGE,
    Math.max(insets.top + SCREEN_EDGE, roomBelow - menuHeight),
  );
  // Left-aligned on the pressed view, like the Files menu, then held inside the
  // gutters so a tile that starts near the right edge does not push it out.
  const left = clamp(anchor.x, SCREEN_EDGE, screenWidth - SCREEN_EDGE - MENU_WIDTH);

  const previewScale = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [1, PREVIEW_SCALE],
  });
  const cardScale = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [0.92, 1],
  });
  // Same fade as before, floored at `CARD_MIN_OPACITY` so the glass card is
  // never handed the one value its material refuses to draw on.
  const cardOpacity = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [CARD_MIN_OPACITY, 1],
  });

  /**
   * Plays the exit, then hands control back to the caller.
   *
   * The caller keeps `visible` true for the length of the animation — it only
   * learns about the dismissal through `onClose`, once the menu has faded — which
   * is what makes the fade-out possible without a second piece of state tracking
   * whether the modal is still on screen.
   *
   * A row that opens something else waits one frame past the close, by which time
   * the unmount has been committed. One code path on both platforms, unlike
   * waiting on iOS's `onDismiss`, which Android never fires.
   */
  const requestClose = (action?: () => void) => {
    // A call in flight owns the menu: hiding it would strand the spinner and
    // leave the user unsure whether the request went out.
    if (isBusy) return;
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
      // The appearance is animated here, anchored to the pressed view; the
      // platform transitions would slide or fade the whole screen instead.
      animationType="none"
      statusBarTranslucent
      onRequestClose={() => requestClose()}
    >
      <View style={styles.root}>
        <Animated.View
          style={[StyleSheet.absoluteFill, { opacity: progress }]}
          pointerEvents="none"
        >
          {/* Still a blur, and deliberately not a glass surface: Liquid Glass is
              the material of a *panel*, and this is the whole screen behind the
              menu — iOS blurs the background behind its own context menu rather
              than glassing it, and there is nothing here for glass to be the
              panel of. (expo/expo#42501 is worth watching: glass and blur
              coexisting on SDK 55 / iOS 26 can produce render artifacts, and
              this screen now holds one of each. The first thing to try would be
              dropping this backdrop to its scrim alone.) */}
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
          testID={`${testIDPrefix}-backdrop`}
        />

        {/* The pressed view, redrawn on its own rect and lifted. Inert: a tap on
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
          {renderPreview(target)}
        </Animated.View>

        <Animated.View
          style={[
            styles.cardWrapper,
            {
              top,
              left,
              opacity: cardOpacity,
              transform: [{ scale: cardScale }],
              transformOrigin: opensDown ? "top left" : "bottom left",
            },
          ]}
          testID={`${testIDPrefix}-menu`}
        >
          <GlassSurface style={styles.card}>
            {actions.map((action, index) => (
              <Fragment key={action.key}>
                {/* The one line in the card, and the only thing separating the
                    destructive action from the reversible ones. */}
                {action.destructive && index > 0 ? (
                  <View style={styles.divider} />
                ) : null}
                <MenuRow
                  icon={action.icon}
                  label={action.label}
                  onPress={
                    action.closesMenu
                      ? () => requestClose(action.onPress)
                      : action.onPress
                  }
                  disabled={isBusy}
                  isBusy={action.isBusy}
                  destructive={action.destructive}
                  testID={action.testID}
                />
              </Fragment>
            ))}
          </GlassSurface>
        </Animated.View>
      </View>
    </Modal>
  );
}

/**
 * One line of the menu: a glyph, a label, nothing else.
 *
 * No description, no circled icon, no chevron — no action opens a submenu, and
 * the compactness is what makes this read as a context menu rather than a sheet.
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
    // `overflow: hidden` the rounded material needs.
    ...Shadows.soft,
  },
  card: {
    borderRadius: BorderRadius.xl,
    paddingVertical: CARD_PADDING_VERTICAL,
    overflow: "hidden",
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
