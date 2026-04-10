package com.idp.erp.dto;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Data @Builder
public class StudentResponse {
    private String id;
    private String fullName;
    private String email;
    private String phone;
    private LocalDate dateOfBirth;
    private String courseApplied;
    private LocalDateTime createdAt;
}
