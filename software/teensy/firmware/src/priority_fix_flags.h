#pragma once

namespace priority_fix_flags
{
inline constexpr bool kEnableAllPriorityFixes = false;

inline constexpr bool kFixIssue57RescueWallTurnDirection = true;
inline constexpr bool kFixIssue58Case12ControlFlow = true;
inline constexpr bool kFixIssue59ServiceStateMachinesDuringMotion = true;
inline constexpr bool kFixIssue60RunDistanceTimeout = true;
inline constexpr bool kFixIssue61ColorSensorTimeout = true;
inline constexpr bool kFixIssue62VisibleSensorInitFailures = true;
inline constexpr bool kFixIssue63KeepSerialDuringMotions = false;
inline constexpr bool kFixIssue67InitializeMotorPulseCount = true;
inline constexpr bool kFixIssue74ValidateSerialPayloads = true;
inline constexpr bool kFixIssue75SerialTelemetry = true;
inline constexpr bool kFixIssue76DocumentSerialProtocol = true;
inline constexpr bool kFixIssue112RunAngleTimeout = true;
} // namespace priority_fix_flags
