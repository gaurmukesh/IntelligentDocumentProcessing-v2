package com.idp.erp.client;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.util.Map;

/**
 * HTTP client for FastAPI AI service.
 *
 * Calls:
 *   POST /verify/{applicationId}          — trigger async document validation
 *   GET  /applications/{applicationId}/pipeline-status  — poll pipeline state
 *   GET  /verify/{applicationId}/report   — fetch full verification report
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AiServiceClient {

    private final WebClient aiServiceWebClient;

    /**
     * Ask FastAPI to start validation for an application.
     * FastAPI runs the pipeline async and calls back via POST /api/applications/{id}/verification-result.
     *
     * @return true if FastAPI accepted the request (2xx)
     */
    public boolean triggerVerification(String applicationId) {
        try {
            aiServiceWebClient.post()
                    .uri("/verify/{id}", applicationId)
                    .retrieve()
                    .toBodilessEntity()
                    .block();
            log.info("Triggered verification for application {}", applicationId);
            return true;
        } catch (WebClientResponseException e) {
            log.error("FastAPI rejected verification trigger for {}: {} {}",
                    applicationId, e.getStatusCode(), e.getResponseBodyAsString());
            return false;
        } catch (Exception e) {
            log.error("Failed to trigger verification for {}: {}", applicationId, e.getMessage());
            return false;
        }
    }

    /**
     * Poll FastAPI for the current pipeline stage (UPLOADING / EXTRACTING / VALIDATING / COMPLETE / FAILED).
     *
     * @return map with pipeline_stage and nested fields, or empty map on error
     */
    public Map<String, Object> getPipelineStatus(String applicationId) {
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> result = aiServiceWebClient.get()
                    .uri("/applications/{id}/pipeline-status", applicationId)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .block();
            return result != null ? result : Map.of();
        } catch (WebClientResponseException e) {
            log.error("FastAPI pipeline status error for {}: {} {}",
                    applicationId, e.getStatusCode(), e.getResponseBodyAsString());
            return Map.of();
        } catch (Exception e) {
            log.error("Failed to fetch pipeline status for {}: {}", applicationId, e.getMessage());
            return Map.of();
        }
    }

    /**
     * Fetch the full verification report from FastAPI.
     *
     * @return report as raw map (serialised to verificationReport JSON column), or empty map on error
     */
    public Map<String, Object> getVerificationReport(String applicationId) {
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> result = aiServiceWebClient.get()
                    .uri("/verify/{id}/report", applicationId)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .block();
            return result != null ? result : Map.of();
        } catch (WebClientResponseException e) {
            log.error("FastAPI report error for {}: {} {}",
                    applicationId, e.getStatusCode(), e.getResponseBodyAsString());
            return Map.of();
        } catch (Exception e) {
            log.error("Failed to fetch verification report for {}: {}", applicationId, e.getMessage());
            return Map.of();
        }
    }
}
