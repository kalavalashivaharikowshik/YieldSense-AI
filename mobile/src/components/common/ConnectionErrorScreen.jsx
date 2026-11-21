import { StyleSheet, Text, View } from "react-native";

import { colors } from "../../constants/colors";
import AppButton from "./AppButton";

function ConnectionErrorScreen({ onRetry }) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Unable to reach YieldSense AI</Text>

      <Text style={styles.message}>
        Check your internet connection. The server may also be starting up,
        which can take a moment. You are still signed in.
      </Text>

      <AppButton title="Try again" onPress={onRetry} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    padding: 24,
    backgroundColor: colors.background,
  },

  title: {
    fontSize: 20,
    fontWeight: "700",
    color: colors.text,
    textAlign: "center",
  },

  message: {
    marginTop: 10,
    marginBottom: 24,
    fontSize: 15,
    lineHeight: 22,
    color: colors.textSecondary,
    textAlign: "center",
  },
});

export default ConnectionErrorScreen;
