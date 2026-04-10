package com.idp.erp.repository;

import com.idp.erp.entity.DocumentRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface DocumentRecordRepository extends JpaRepository<DocumentRecord, String> {
    List<DocumentRecord> findByApplicationId(String applicationId);
}
