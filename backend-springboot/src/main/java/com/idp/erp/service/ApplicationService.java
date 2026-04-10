package com.idp.erp.service;

import com.idp.erp.dto.ApplicationRequest;
import com.idp.erp.dto.ApplicationResponse;
import com.idp.erp.dto.StatusUpdateRequest;
import com.idp.erp.entity.Application;
import com.idp.erp.entity.Application.ApplicationStatus;
import com.idp.erp.entity.Student;
import com.idp.erp.repository.ApplicationRepository;
import com.idp.erp.repository.StudentRepository;
import jakarta.persistence.EntityNotFoundException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ApplicationService {

    private final ApplicationRepository applicationRepository;
    private final StudentRepository studentRepository;

    public ApplicationResponse create(ApplicationRequest request) {
        Student student = studentRepository.findById(request.getStudentId())
                .orElseThrow(() -> new EntityNotFoundException("Student not found: " + request.getStudentId()));

        Application application = Application.builder()
                .student(student)
                .status(ApplicationStatus.DRAFT)
                .verificationDecision(Application.VerificationDecision.PENDING)
                .build();

        return toResponse(applicationRepository.save(application));
    }

    public ApplicationResponse getById(String id) {
        Application application = applicationRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Application not found: " + id));
        return toResponse(application);
    }

    public List<ApplicationResponse> getAll(ApplicationStatus status) {
        List<Application> applications = (status != null)
                ? applicationRepository.findByStatus(status)
                : applicationRepository.findAll();
        return applications.stream().map(this::toResponse).collect(Collectors.toList());
    }

    public List<ApplicationResponse> getByStudent(String studentId) {
        return applicationRepository.findByStudentId(studentId)
                .stream().map(this::toResponse).collect(Collectors.toList());
    }

    public ApplicationResponse updateStatus(String id, StatusUpdateRequest request) {
        Application application = applicationRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Application not found: " + id));

        application.setStatus(request.getStatus());
        if (request.getVerificationDecision() != null) {
            application.setVerificationDecision(request.getVerificationDecision());
        }
        if (request.getVerificationScore() != null) {
            application.setVerificationScore(request.getVerificationScore());
        }
        if (request.getDecisionReason() != null) {
            application.setDecisionReason(request.getDecisionReason());
        }
        if (request.getVerificationReport() != null) {
            application.setVerificationReport(request.getVerificationReport());
        }
        return toResponse(applicationRepository.save(application));
    }

    private ApplicationResponse toResponse(Application app) {
        return ApplicationResponse.builder()
                .id(app.getId())
                .studentId(app.getStudent().getId())
                .studentName(app.getStudent().getFullName())
                .courseApplied(app.getStudent().getCourseApplied())
                .status(app.getStatus())
                .verificationDecision(app.getVerificationDecision())
                .verificationScore(app.getVerificationScore())
                .decisionReason(app.getDecisionReason())
                .createdAt(app.getCreatedAt())
                .updatedAt(app.getUpdatedAt())
                .build();
    }
}
