import apiClient from "../api/apiClient";
import predictionApi from "../api/predictionApi";
import { downloadBlob, getDownloadFilename } from "../utils/download";

async function downloadPredictionReport(
  format,
  params = {}
) {
  const response = await apiClient.get(
    `/reports/predictions/${format}`,
    {
      params,
      responseType: "blob",
    }
  );

  const filename = getDownloadFilename(
    response.headers[
      "content-disposition"
    ],
    `yield_predictions.${format}`
  );

  downloadBlob(
    response.data,
    filename
  );

  return filename;
}

export const predictionService = {
  async createPrediction(payload) {
    const response =
      await predictionApi.post(
        "",
        payload
      );

    return response.data;
  },

  async getPredictions(params = {}) {
    const response =
      await predictionApi.get("", {
        params,
      });

    return response.data;
  },

  async getPrediction(id) {
    const response =
      await predictionApi.get(
        `/${id}`
      );

    return response.data;
  },

  async getPredictionSummary(
    params = {}
  ) {
    const response =
      await predictionApi.get(
        "/summary",
        {
          params,
        }
      );

    return response.data;
  },

  async getModelInformation() {
    const response =
      await predictionApi.get(
        "/model/info"
      );

    return response.data;
  },

  async exportPredictionsCsv(
    params = {}
  ) {
    return downloadPredictionReport(
      "csv",
      params
    );
  },

  async exportPredictionsPdf(
    params = {}
  ) {
    return downloadPredictionReport(
      "pdf",
      params
    );
  },
};