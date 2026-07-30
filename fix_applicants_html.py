import sys

file_path = r'c:\Users\jtcor\Documents\capstone\templates\staff\applicants.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

config_script = '''<script>
    window.APPLICANTS_CONFIG = {
        userPosition: '{{ request.user.position }}',
        duplicatePreviewUrl: '{% url "intake:duplicate_preview" request.user.position %}',
        evaluationApplicationsUrl: '{% url "applications:applications_list" request.user.position %}',
        applicantRequirementScanStatusUrl: '{% url "intake:applicant_requirement_scan_status" request.user.position %}',
        removeScannedRequirementUrl: '{% url "intake:remove_scanned_requirement" request.user.position %}',
        uploadScannedRequirementUrl: '{% url "intake:upload_scanned_requirement" request.user.position %}',
        deleteApplicantUrl: '{% url "intake:delete_applicant" request.user.position %}',
        blacklistRegistryUrl: '{% url "units:blacklist_management" request.user.position %}',
        proceedToApplicationsUrl: '{% url "intake:proceed_to_applications" request.user.position %}',
        updateApplicantUrl: '{% url "intake:update_applicant" request.user.position %}',
        updateEligibilityUrl: '{% url "intake:update_eligibility" request.user.position %}',
        archiveListUrl: '{% url "intake:archive_list" request.user.position %}',
        walkinRegisterUrl: '{% url "intake:walkin_register" request.user.position %}',
        updateCdrrmoStatusUrl: '{% url "applications:update_cdrrmo_status" request.user.position %}',
        updateCdrrmoCertificationUrl: '{% url "applications:update_cdrrmo_certification" request.user.position %}'
    };
</script>
'''

content = content.replace('<script src=\"{% static \'js/applicants.js\' %}\"></script>', config_script + '<script src=\"{% static \'js/applicants.js\' %}\"></script>')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
