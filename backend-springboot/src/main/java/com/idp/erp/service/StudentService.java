package com.idp.erp.service;

import com.idp.erp.dto.StudentRequest;
import com.idp.erp.dto.StudentResponse;
import com.idp.erp.entity.Student;
import com.idp.erp.repository.StudentRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class StudentService {

    private final StudentRepository studentRepository;

    public StudentResponse register(StudentRequest request) {
        if (studentRepository.existsByEmail(request.getEmail())) {
            throw new IllegalArgumentException("Student with email " + request.getEmail() + " already exists");
        }
        Student student = Student.builder()
                .fullName(request.getFullName())
                .email(request.getEmail())
                .phone(request.getPhone())
                .dateOfBirth(request.getDateOfBirth())
                .courseApplied(request.getCourseApplied())
                .build();
        return toResponse(studentRepository.save(student));
    }

    public StudentResponse getById(String id) {
        Student student = studentRepository.findById(id)
                .orElseThrow(() -> new jakarta.persistence.EntityNotFoundException("Student not found: " + id));
        return toResponse(student);
    }

    public List<StudentResponse> getAll() {
        return studentRepository.findAll().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    private StudentResponse toResponse(Student student) {
        return StudentResponse.builder()
                .id(student.getId())
                .fullName(student.getFullName())
                .email(student.getEmail())
                .phone(student.getPhone())
                .dateOfBirth(student.getDateOfBirth())
                .courseApplied(student.getCourseApplied())
                .createdAt(student.getCreatedAt())
                .build();
    }
}
