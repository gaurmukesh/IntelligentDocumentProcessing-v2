package com.idp.erp.repository;

import com.idp.erp.entity.Application;
import com.idp.erp.entity.Application.ApplicationStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ApplicationRepository extends JpaRepository<Application, String> {
    List<Application> findByStudentId(String studentId);
    List<Application> findByStatus(ApplicationStatus status);
}
