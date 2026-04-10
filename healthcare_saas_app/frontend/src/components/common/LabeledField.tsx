/**
 * LabeledField Component
 * A reusable form field component with label, input, and validation display
 * Used throughout the application for consistent form field styling and behavior
 */

import React, { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import infoIcon from "../../assets/info-icon.svg";
import type { LabeledFieldProps } from "../../types/app";

export function LabeledField(props: LabeledFieldProps) {
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = props.type === "password";
  
  return (
    <div className="form-field">
      <div className="label-row">
        <label htmlFor={props.id}>
          {props.label}
          {props.required && <span style={{ color: '#ff90ab', marginLeft: '4px' }}>*</span>}
        </label>
        <button 
          className="info-icon" 
          type="button" 
          tabIndex={-1} 
          aria-label={`${props.label} input rules`} 
          data-tip={props.helpText}
        >
          <img src={infoIcon} alt="info" className="info-icon-img" />
        </button>
      </div>
      {props.error && <p className="field-error">{props.error}</p>}
      <div className="input-wrapper">
        {props.children ? (
          props.children
        ) : (
          <input
            id={props.id}
            type={isPassword && !showPassword ? "password" : isPassword && showPassword ? "text" : props.type ?? "text"}
            value={props.value}
            placeholder={props.placeholder}
            onChange={(event) => props.onChange(event.target.value)}
            autoComplete={props.autoComplete || "off"}
            required={props.required}
          />
        )}
        {isPassword && !props.children && (
          <button
            type="button"
            className="password-toggle"
            tabIndex={-1}
            onClick={() => setShowPassword(!showPassword)}
            aria-label={showPassword ? "Hide password" : "Show password"}
          >
            {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
          </button>
        )}
      </div>
    </div>
  );
}
