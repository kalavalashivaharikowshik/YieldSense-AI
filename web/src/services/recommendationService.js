import apiClient from "../api/apiClient";
import recommendationApi from "../api/recommendationApi";
import { downloadBlob, getDownloadFilename } from "../utils/download";

async function downloadRecommendationReport(
  format,
  params = {}
) {
  const response = await apiClient.get(
    `/reports/recommendations/${format}`,
    {
      params,
      responseType: "blob",
    }
  );

  const filename = getDownloadFilename(
    response.headers[
      "content-disposition"
    ],
    `crop_recommendations.${format}`
  );

  downloadBlob(
    response.data,
    filename
  );

  return filename;
}

export async function generateRecommendation(
  data
) {
  const response =
    await recommendationApi.post(
      "",
      data
    );

  return response.data;
}

export async function getRecommendationHistory(
  params = {}
) {
  const response =
    await recommendationApi.get(
      "/history",
      {
        params,
      }
    );

  return response.data;
}

export async function getRecommendation(
  id
) {
  const response =
    await recommendationApi.get(
      `/${id}`
    );

  return response.data;
}

export async function exportRecommendationsCsv(
  params = {}
) {
  return downloadRecommendationReport(
    "csv",
    params
  );
}

export async function exportRecommendationsPdf(
  params = {}
) {
  return downloadRecommendationReport(
    "pdf",
    params
  );
}