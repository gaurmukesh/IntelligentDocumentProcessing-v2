package com.idp.erp.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class AiServiceConfig {

    @Value("${ai.service.base-url}")
    private String aiServiceBaseUrl;

    @Bean
    public WebClient aiServiceWebClient() {
        return WebClient.builder()
                .baseUrl(aiServiceBaseUrl)
                .defaultHeader("Content-Type", "application/json")
                .build();
    }
}
