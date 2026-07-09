import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";

interface Props {
  connected: boolean;
  baseUrl: string;
  environmentName: string;
}

const ConnectionStatus: React.FC<Props> = ({ connected, baseUrl, environmentName }) => {
  return (
    <View style={styles.container}>
      <Ionicons
        name={connected ? "checkmark-circle-outline" : "close-circle-outline"}
        size={20}
        color={connected ? "#28a745" : "#dc3545"}
      />
      <Text style={styles.text}>
        {connected ? "Connecté" : "Hors ligne"} - {environmentName} ({baseUrl})
      </Text>
    </View>
  );
};

export default ConnectionStatus;

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    padding: 10,
    backgroundColor: "#fff",
    borderRadius: 10,
    marginVertical: 10,
  },
  text: {
    marginLeft: 10,
    color: "#333",
  },
});