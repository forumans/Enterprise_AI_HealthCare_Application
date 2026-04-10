/**
 * Patient Profile Page Component
 * Allows patients to update their profile information
 * Includes personal details, address, and insurance information
 */

import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { StatusMessage } from "../common/StatusMessage";
import type { SessionState } from "../../types/app";

interface PatientProfilePageProps {
  auth: any;
  userData: any;
}

// List of countries for dropdown
const COUNTRIES = [
  "United States",
  "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo, Democratic Republic of the", "Congo, Republic of the", "Costa Rica", "Cote d'Ivoire", "Croatia", "Cuba", "Cyprus", "Czechia", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"
];

// LabeledField component defined outside to prevent re-creation
const LabeledField = (props: {
  id: string;
  label: string;
  helpText: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  error?: string;
  autoComplete?: string;
}) => {
  return (
    <div className="form-field">
      <div className="label-row">
        <label htmlFor={props.id}>{props.label}</label>
        <button className="info-icon" type="button" tabIndex={-1} aria-label={`${props.label} input rules`} data-tip={props.helpText}>
          <div style={{
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            backgroundColor: '#42b5f5',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '10px',
            fontWeight: 'bold',
            cursor: 'help'
          }}>i</div>
        </button>
      </div>
      {props.error && <p className="field-error">{props.error}</p>}
      <div className="input-wrapper">
        <input
          id={props.id}
          key={props.id}
          type={props.type ?? "text"}
          value={props.value}
          placeholder={props.placeholder}
          onChange={(event) => props.onChange(event.target.value)}
          autoComplete={props.autoComplete || "off"}
          tabIndex={0}
        />
      </div>
    </div>
  );
};

interface FieldErrors {
  fullName?: string;
  phone?: string;
  dateOfBirth?: string;
}

export function PatientProfilePage({ auth, userData }: PatientProfilePageProps) {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [gender, setGender] = useState("");
  const [addressLine1, setAddressLine1] = useState("");
  const [addressLine2, setAddressLine2] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [country, setCountry] = useState("United States");
  const [insuranceProvider, setInsuranceProvider] = useState("");
  const [insurancePolicyNumber, setInsurancePolicyNumber] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // Load current patient data on component mount
  useEffect(() => {
    const loadPatientData = async () => {
      try {
        const data = await api.getPatientProfile(auth.session.accessToken);
        
        setFullName(data.full_name || "");
        setPhone(data.phone || "");
        setDateOfBirth(data.date_of_birth || "");
        // Normalize gender value to match dropdown options
        let normalizedGender = "";
        if (data.gender) {
          const genderLower = data.gender.toLowerCase();
          switch (genderLower) {
            case "male":
              normalizedGender = "MALE";
              break;
            case "female":
              normalizedGender = "FEMALE";
              break;
            case "other":
              normalizedGender = "OTHER";
              break;
            case "prefer_not_to_say":
            case "prefer not to say":
              normalizedGender = "PREFER_NOT_TO_SAY";
              break;
            default:
              // If it's already uppercase or unknown, use as-is
              normalizedGender = data.gender.toUpperCase();
          }
        }
        setGender(normalizedGender);
        setAddressLine1(data.address_line1 || "");
        setAddressLine2(data.address_line2 || "");
        setCity(data.city || "");
        setState(data.state || "");
        setPostalCode(data.postal_code || "");
        setCountry(data.country || "United States");
        setInsuranceProvider(data.insurance_provider || "");
        setInsurancePolicyNumber(data.insurance_policy_number || "");
      } catch (error) {
        console.error("Failed to load patient profile:", error);
        setErrorMessage(error.message || "Failed to load profile");
      }
    };

    if (auth.session.accessToken) {
      loadPatientData();
    }
  }, [auth.session.accessToken]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitAttempted(true);
    
    const nextErrors: FieldErrors = {};
    
    if (fullName.trim().length < 3) {
      nextErrors.fullName = "Name must be at least 3 characters.";
    }
    if (!/^\+?[0-9\-\s]{10,15}$/.test(phone)) {
      nextErrors.phone = "Phone should be 10-15 digits.";
    }
    
    // Validate date of birth if provided
    if (dateOfBirth) {
      const dob = new Date(dateOfBirth);
      const today = new Date();
      const maxDate = new Date();
      maxDate.setFullYear(today.getFullYear() - 120);
      
      if (dob > today) {
        nextErrors.dateOfBirth = "Date of birth cannot be in the future.";
      } else if (dob < maxDate) {
        nextErrors.dateOfBirth = "Date of birth cannot be more than 120 years ago.";
      }
    }
    
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }

    setLoading(true);
    try {
      const updatePayload = {
        fullName: fullName.trim(),
        phone: phone.trim(),
        dateOfBirth: dateOfBirth || undefined,
        gender: gender || undefined,
        addressLine1: addressLine1.trim() || undefined,
        addressLine2: addressLine2.trim() || undefined,
        city: city.trim() || undefined,
        state: state.trim() || undefined,
        postalCode: postalCode.trim() || undefined,
        country: country || undefined,
        insuranceProvider: insuranceProvider.trim() || undefined,
        insurancePolicyNumber: insurancePolicyNumber.trim() || undefined
      };
      
      await api.updatePatientProfile(auth.session.accessToken, updatePayload);
      
      setSuccessMessage("Profile updated successfully!");
      
      // Refresh patient details
      await userData.loadPatientDetails();
      
      setTimeout(() => {
        setSuccessMessage("");
        // Navigate to Schedule Appointments page after successful update
        navigate("/patients/appointments");
      }, 1500);
    } catch (error) {
      console.error("Failed to update profile:", error);
      alert("Failed to update profile. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Update Profile</h2>
      
      <div className="card" style={{ padding: '24px', maxWidth: '600px', margin: '0 auto' }}>
        {successMessage && (
          <StatusMessage message={successMessage} type="success" />
        )}
        
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <LabeledField 
            id="profile-full-name" 
            label="Full Name" 
            helpText="Name must be 3-80 characters." 
            value={fullName} 
            onChange={setFullName} 
            error={submitAttempted ? errors.fullName : undefined}
            autoComplete="off" 
          />
          
          <LabeledField 
            id="profile-phone" 
            label="Phone" 
            helpText="Use 10-15 digits. Country code allowed." 
            value={phone} 
            onChange={setPhone} 
            error={submitAttempted ? errors.phone : undefined}
            autoComplete="off" 
          />
          
          <LabeledField 
            id="profile-date-of-birth" 
            label="Date of Birth" 
            helpText="Format: MM/DD/YYYY (optional, max age 120 years)." 
            value={dateOfBirth} 
            onChange={setDateOfBirth} 
            type="date" 
            error={submitAttempted ? errors.dateOfBirth : undefined}
            autoComplete="off" 
          />
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb' }}>Gender</label>
            <select 
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              tabIndex={0}
              style={{
                padding: '11px 12px',
                borderRadius: '10px',
                border: '1px solid rgba(136, 194, 227, 0.36)',
                fontSize: '14px',
                backgroundColor: 'rgba(9, 35, 55, 0.82)',
                color: '#eef8ff',
                width: '100%'
              }}
            >
              <option value="">Select Gender (Optional)</option>
              <option value="MALE">Male</option>
              <option value="FEMALE">Female</option>
              <option value="OTHER">Other</option>
              <option value="PREFER_NOT_TO_SAY">Prefer not to say</option>
            </select>
          </div>
          
          <LabeledField 
            id="profile-address-line1" 
            label="Address Line 1" 
            helpText="Street address (optional)." 
            value={addressLine1} 
            onChange={setAddressLine1} 
          />
          
          <LabeledField 
            id="profile-address-line2" 
            label="Address Line 2" 
            helpText="Apartment, suite, unit, building, floor, etc. (optional)." 
            value={addressLine2} 
            onChange={setAddressLine2} 
          />
          
          <LabeledField 
            id="profile-city" 
            label="City" 
            helpText="City name (optional)." 
            value={city} 
            onChange={setCity} 
          />
          
          <LabeledField 
            id="profile-state" 
            label="State/Province" 
            helpText="State or province (optional)." 
            value={state} 
            onChange={setState} 
          />
          
          <LabeledField 
            id="profile-postal-code" 
            label="Postal Code" 
            helpText="ZIP or postal code (optional)." 
            value={postalCode} 
            onChange={setPostalCode} 
          />
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb' }}>Country</label>
            <select 
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              tabIndex={0}
              style={{
                padding: '11px 12px',
                borderRadius: '10px',
                border: '1px solid rgba(136, 194, 227, 0.36)',
                fontSize: '14px',
                backgroundColor: 'rgba(9, 35, 55, 0.82)',
                color: '#eef8ff',
                width: '100%'
              }}
            >
              {COUNTRIES.map(country => (
                <option key={country} value={country}>{country}</option>
              ))}
            </select>
          </div>
          
          <LabeledField 
            id="profile-insurance-provider" 
            label="Insurance Provider" 
            helpText="Insurance company name (optional)." 
            value={insuranceProvider} 
            onChange={setInsuranceProvider} 
            autoComplete="off" 
          />
          
          <LabeledField 
            id="profile-insurance-policy" 
            label="Policy Number" 
            helpText="Insurance policy number (optional)." 
            value={insurancePolicyNumber} 
            onChange={setInsurancePolicyNumber} 
            autoComplete="off" 
          />
          
          <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
            <button 
              type="submit" 
              disabled={loading}
              tabIndex={0}
              style={{
                flex: '1',
                padding: '12px 24px',
                fontSize: '16px',
                fontWeight: '500',
                backgroundColor: loading ? '#94a3b8' : '#42b5f5',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.6 : 1
              }}
            >
              {loading ? 'Updating...' : 'Update Profile'}
            </button>
            <button 
              type="button"
              onClick={() => navigate("/patients/appointments")}
              disabled={loading}
              tabIndex={0}
              style={{
                flex: '1',
                padding: '12px 24px',
                fontSize: '16px',
                fontWeight: '500',
                backgroundColor: loading ? '#94a3b8' : '#6c757d',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.6 : 1
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
