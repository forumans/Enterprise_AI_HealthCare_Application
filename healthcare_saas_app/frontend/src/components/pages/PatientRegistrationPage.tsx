/**
 * Patient Registration Page Component
 * Allows new patients to create an account
 * Includes personal details, contact information, and insurance details
 */

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { api } from "../../api";

interface FieldErrors {
  name?: string;
  email?: string;
  phone?: string;
  password?: string;
  dateOfBirth?: string;
}

// Email validation function
function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

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
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = props.type === "password";
  
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
          type={isPassword && !showPassword ? "password" : isPassword && showPassword ? "text" : props.type ?? "text"}
          value={props.value}
          placeholder={props.placeholder}
          onChange={(event) => props.onChange(event.target.value)}
          autoComplete={props.autoComplete || "off"}
          tabIndex={0}
        />
        {isPassword && (
          <button
            type="button"
            className="password-toggle"
            onClick={() => setShowPassword(!showPassword)}
            aria-label={showPassword ? "Hide password" : "Show password"}
            tabIndex={-1}
            style={{
              position: 'absolute',
              right: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#42b5f5'
            }}
          >
            {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
          </button>
        )}
      </div>
    </div>
  );
};

// List of countries for dropdown
const COUNTRIES = [
  "United States",
  "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo, Democratic Republic of the", "Congo, Republic of the", "Costa Rica", "Cote d'Ivoire", "Croatia", "Cuba", "Cyprus", "Czechia", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"
];

export function PatientRegistrationPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [gender, setGender] = useState("");
  const [addressLine1, setAddressLine1] = useState("");
  const [addressLine2, setAddressLine2] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [country, setCountry] = useState("United States");
  const [insurance, setInsurance] = useState("");
  const [policy, setPolicy] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const nextErrors: FieldErrors = {};
    
    if (name.trim().length < 3) {
      nextErrors.name = "Name must be at least 3 characters.";
    }
    if (!validateEmail(email)) {
      nextErrors.email = "Please provide a valid email address.";
    }
    if (!/^\+?[0-9\-\s]{10,15}$/.test(phone)) {
      nextErrors.phone = "Phone should be 10-15 digits.";
    }
    if (password.length < 5) {
      nextErrors.password = "Password must be at least 5 characters.";
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
    if (Object.keys(nextErrors).length === 0) {
      setLoading(true);
      try {
        await api.registerPatient({
          full_name: name.trim(),
          email: email.trim(),
          phone: phone.trim(),
          password: password,
          date_of_birth: dateOfBirth || undefined,
          gender: gender || undefined,
          address_line1: addressLine1.trim() || undefined,
          address_line2: addressLine2.trim() || undefined,
          city: city.trim() || undefined,
          state: state.trim() || undefined,
          postal_code: postalCode.trim() || undefined,
          country: country || undefined,
          insurance_provider: insurance.trim() || undefined,
          insurance_policy_number: policy.trim() || undefined
        });
        
        alert("Registration successful! Please log in.");
        navigate("/patients/login");
      } catch (error) {
        console.error("Registration failed:", error);
        alert("Registration failed. Please try again.");
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Patient Registration</h2>
      
      <div className="card" style={{ padding: '24px', maxWidth: '600px', margin: '0 auto' }}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <LabeledField 
            key="register-name"
            id="register-name" 
            label="Full Name" 
            helpText="Name must be 3-80 characters." 
            value={name} 
            onChange={setName} 
            error={errors.name} 
            autoComplete="off" 
          />
          
          <LabeledField 
            key="register-email"
            id="register-email" 
            label="Email" 
            helpText="Use a valid email format, e.g., name@example.com." 
            value={email} 
            onChange={setEmail} 
            error={errors.email} 
            autoComplete="off" 
          />
          
          <LabeledField 
            key="register-phone"
            id="register-phone" 
            label="Phone" 
            helpText="Use 10-15 digits. Country code allowed." 
            value={phone} 
            onChange={setPhone} 
            error={errors.phone} 
            autoComplete="off" 
          />
          
          <LabeledField 
            key="register-password"
            id="register-password" 
            label="Password" 
            helpText="Minimum 5 characters." 
            value={password} 
            onChange={setPassword} 
            type="password" 
            error={errors.password} 
            autoComplete="new-password" 
          />
          
          <LabeledField 
            key="register-date-of-birth"
            id="register-date-of-birth" 
            label="Date of Birth" 
            helpText="Format: MM/DD/YYYY (optional, max age 120 years)." 
            value={dateOfBirth} 
            onChange={setDateOfBirth} 
            type="date" 
            error={errors.dateOfBirth} 
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
            key="register-address-line1"
            id="register-address-line1" 
            label="Address Line 1" 
            helpText="Street address (optional)." 
            value={addressLine1} 
            onChange={setAddressLine1} 
            autoComplete="off" 
          />
          
          <LabeledField 
            key="register-address-line2"
            id="register-address-line2" 
            label="Address Line 2" 
            helpText="Apartment, suite, unit, building, floor, etc. (optional)." 
            value={addressLine2} 
            onChange={setAddressLine2} 
            autoComplete="off" 
          />
          
          <LabeledField 
            key="register-city"
            id="register-city" 
            label="City" 
            helpText="City name (optional)." 
            value={city} 
            onChange={setCity} 
            autoComplete="off" 
          />
          
          <LabeledField 
            key="register-state"
            id="register-state" 
            label="State/Province" 
            helpText="State or province (optional)." 
            value={state} 
            onChange={setState} 
            autoComplete="off" 
          />
          
          <LabeledField 
            key="register-postal-code"
            id="register-postal-code" 
            label="Postal Code" 
            helpText="ZIP or postal code (optional)." 
            value={postalCode} 
            onChange={setPostalCode} 
            autoComplete="off" 
          />
          
          <div key="register-country" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
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
            key="register-insurance"
            id="register-insurance" 
            label="Insurance Provider" 
            helpText="Insurance company name (optional)." 
            value={insurance} 
            onChange={setInsurance} 
            autoComplete="off" 
          />
          
          <LabeledField 
            key="register-policy"
            id="register-policy" 
            label="Policy Number" 
            helpText="Insurance policy number (optional)." 
            value={policy} 
            onChange={setPolicy} 
            autoComplete="off" 
          />
          
          <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
            <button 
              type="submit" 
              disabled={loading}
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
              {loading ? 'Creating Account...' : 'Create Account'}
            </button>
            <button 
              type="button"
              onClick={() => navigate("/patients/login")}
              disabled={loading}
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
