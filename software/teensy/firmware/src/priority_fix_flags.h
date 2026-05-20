#pragma once

namespace priority_fix_flags
{
inline constexpr bool kEnableAllPriorityFixes = true;

inline constexpr bool kFixIssue57RescueWallTurnDirection = false;
inline constexpr bool kFixIssue58Case12ControlFlow = false;
inline constexpr bool kFixIssue59ServiceStateMachinesDuringMotion = false;
inline constexpr bool kFixIssue60RunDistanceTimeout = false;
inline constexpr bool kFixIssue61ColorSensorTimeout = false;
inline constexpr bool kFixIssue62VisibleSensorInitFailures = false;
inline constexpr bool kFixIssue63KeepSerialDuringMotions = false;
inline constexpr bool kFixIssue67InitializeMotorPulseCount = false;
inline constexpr bool kFixIssue74ValidateSerialPayloads = false;
inline constexpr bool kFixIssue75SerialTelemetry = false;
inline constexpr bool kFixIssue76DocumentSerialProtocol = false;
inline constexpr bool kFixIssue112RunAngleTimeout = false;
} // namespace priority_fix_flags
