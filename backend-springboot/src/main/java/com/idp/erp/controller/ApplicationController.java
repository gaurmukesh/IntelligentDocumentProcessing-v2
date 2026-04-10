package com.idp.erp.controller;

import com.idp.erp.dto.ApplicationRequest;
import com.idp.erp.dto.ApplicationResponse;
import com.idp.erp.dto.StatusUpdateRequest;
import com.idp.erp.dto.VerificationCallbackRequest;
import com.idp.erp.entity.Application.ApplicationStatus;
import com.idp.erp.service.ApplicationService;
import com.idp.erp.service.VerificationService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/applications")
@RequiredArgsConstructor
public class ApplicationController {

    private final ApplicationService applicationService;
    private final VerificationService verificationService;

    @PostMapping
    public ResponseEntity<ApplicationResponse> create(@Valid @RequestBody ApplicationRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(applicationService.create(request));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApplicationResponse> getById(@PathVariable String id) {
        return ResponseEntity.ok(applicationService.getById(id));
    }

    @GetMapping
    public ResponseEntity<List<ApplicationResponse>> getAll(
            @RequestParam(required = false) ApplicationStatus status) {
        return ResponseEntity.ok(applicationService.getAll(status));
    }

    @GetMapping("/student/{studentId}")
    public ResponseEntity<List<ApplicationResponse>> getByStudent(@PathVariable String studentId) {
        return ResponseEntity.ok(applicationService.getByStudent(studentId));
    }

    @PutMapping("/{id}/status")
    public ResponseEntity<ApplicationResponse> updateStatus(
            @PathVariable String id,
            @Valid @RequestBody StatusUpdateRequest request) {
        return ResponseEntity.ok(applicationService.updateStatus(id, request));
    }

    /**
     * Trigger AI document verification for an application.
     * Sets status to UNDER_REVIEW and asks FastAPI to start the pipeline.
     */
    @PostMapping("/{id}/trigger-verification")
    public ResponseEntity<Void> triggerVerification(@PathVariable String id) {
        verificationService.triggerVerification(id);
        return ResponseEntity.accepted().build();
    }

    /**
     * Callback endpoint called by FastAPI when verification is complete.
     * Updates the application with the AI decision.
     */
    @PostMapping("/{id}/verification-result")
    public ResponseEntity<Void> verificationResult(
            @PathVariable String id,
            @Valid @RequestBody VerificationCallbackRequest request) {
        verificationService.applyVerificationResult(id, request);
        return ResponseEntity.ok().build();
    }
}
