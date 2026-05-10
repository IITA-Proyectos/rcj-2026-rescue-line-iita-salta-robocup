#pragma once

namespace priority_fix_flags
{
inline constexpr bool kEnableAllPriorityFixes = false;

inline constexpr bool kFixIssue57RescueWallTurnDirection = false;
inline constexpr bool kFixIssue58Case12ControlFlow = false;
inline constexpr bool kFixIssue59ServiceStateMachinesDuringMotion = false;
inline constexpr bool kFixIssue60RunDistanceTimeout = false;
inline constexpr bool kFixIssue61ColorSensorTimeout = false;
inline constexpr bool kFixIssue62VisibleSensorInitFailures = false;
} // namespace priority_fix_flags
