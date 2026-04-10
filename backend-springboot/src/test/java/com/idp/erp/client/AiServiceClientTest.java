package com.idp.erp.client;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class AiServiceClientTest {

    @Mock private WebClient webClient;
    @Mock private WebClient.RequestBodyUriSpec postUriSpec;
    @Mock private WebClient.RequestBodySpec postBodySpec;
    @Mock private WebClient.ResponseSpec responseSpec;

    // Raw-typed to avoid generic capture issues with Mockito
    @SuppressWarnings("rawtypes")
    @Mock private WebClient.RequestHeadersUriSpec getUriSpec;
    @SuppressWarnings("rawtypes")
    @Mock private WebClient.RequestHeadersSpec getHeadersSpec;

    private AiServiceClient aiServiceClient;

    @BeforeEach
    void setUp() {
        aiServiceClient = new AiServiceClient(webClient);
    }

    // ── triggerVerification ───────────────────────────────────────

    @Test
    void triggerVerification_returnsTrue_onSuccess() {
        when(webClient.post()).thenReturn(postUriSpec);
        when(postUriSpec.uri(anyString(), anyString())).thenReturn(postBodySpec);
        when(postBodySpec.retrieve()).thenReturn(responseSpec);
        when(responseSpec.toBodilessEntity()).thenReturn(Mono.empty());

        assertThat(aiServiceClient.triggerVerification("app-001")).isTrue();
    }

    @Test
    void triggerVerification_returnsFalse_onWebClientResponseException() {
        when(webClient.post()).thenReturn(postUriSpec);
        when(postUriSpec.uri(anyString(), anyString())).thenReturn(postBodySpec);
        when(postBodySpec.retrieve()).thenReturn(responseSpec);
        when(responseSpec.toBodilessEntity()).thenThrow(
                WebClientResponseException.create(404, "Not Found", null, null, null)
        );

        assertThat(aiServiceClient.triggerVerification("app-missing")).isFalse();
    }

    @Test
    void triggerVerification_returnsFalse_onConnectionError() {
        when(webClient.post()).thenReturn(postUriSpec);
        when(postUriSpec.uri(anyString(), anyString())).thenReturn(postBodySpec);
        when(postBodySpec.retrieve()).thenReturn(responseSpec);
        when(responseSpec.toBodilessEntity()).thenThrow(new RuntimeException("Connection refused"));

        assertThat(aiServiceClient.triggerVerification("app-001")).isFalse();
    }

    // ── getPipelineStatus ─────────────────────────────────────────

    @SuppressWarnings({"rawtypes", "unchecked"})
    @Test
    void getPipelineStatus_returnsMap_onSuccess() {
        Map<String, Object> expected = Map.of("pipeline_stage", "COMPLETE");

        doReturn(getUriSpec).when(webClient).get();
        doReturn(getHeadersSpec).when(getUriSpec).uri(anyString(), anyString());
        doReturn(responseSpec).when(getHeadersSpec).retrieve();
        doReturn(Mono.just(expected)).when(responseSpec).bodyToMono(Map.class);

        Map<String, Object> result = aiServiceClient.getPipelineStatus("app-001");

        assertThat(result).containsEntry("pipeline_stage", "COMPLETE");
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    @Test
    void getPipelineStatus_returnsEmptyMap_onError() {
        doReturn(getUriSpec).when(webClient).get();
        doReturn(getHeadersSpec).when(getUriSpec).uri(anyString(), anyString());
        doReturn(responseSpec).when(getHeadersSpec).retrieve();
        doThrow(new RuntimeException("timeout")).when(responseSpec).bodyToMono(Map.class);

        assertThat(aiServiceClient.getPipelineStatus("app-001")).isEmpty();
    }

    // ── getVerificationReport ─────────────────────────────────────

    @SuppressWarnings({"rawtypes", "unchecked"})
    @Test
    void getVerificationReport_returnsMap_onSuccess() {
        Map<String, Object> expected = Map.of("status", "APPROVED", "overall_score", 0.92);

        doReturn(getUriSpec).when(webClient).get();
        doReturn(getHeadersSpec).when(getUriSpec).uri(anyString(), anyString());
        doReturn(responseSpec).when(getHeadersSpec).retrieve();
        doReturn(Mono.just(expected)).when(responseSpec).bodyToMono(Map.class);

        Map<String, Object> result = aiServiceClient.getVerificationReport("app-001");

        assertThat(result).containsEntry("status", "APPROVED");
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    @Test
    void getVerificationReport_returnsEmptyMap_on404() {
        doReturn(getUriSpec).when(webClient).get();
        doReturn(getHeadersSpec).when(getUriSpec).uri(anyString(), anyString());
        doReturn(responseSpec).when(getHeadersSpec).retrieve();
        doThrow(WebClientResponseException.create(404, "Not Found", null, null, null))
                .when(responseSpec).bodyToMono(Map.class);

        assertThat(aiServiceClient.getVerificationReport("app-001")).isEmpty();
    }
}
