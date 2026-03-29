// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract TruVerifySeal {
    struct CertificateRecord {
        address issuer;
        address studentWallet;
        uint256 issuedAt;
        bool exists;
    }

    address public owner;
    mapping(address => bool) public issuers;
    mapping(bytes32 => CertificateRecord) private certificates;

    event IssuerUpdated(address indexed issuer, bool isAuthorized);
    event CertificateIssued(
        bytes32 indexed certificateHash,
        address indexed issuer,
        address indexed studentWallet,
        uint256 issuedAt
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    modifier onlyIssuer() {
        require(issuers[msg.sender], "Only issuer");
        _;
    }

    constructor() {
        owner = msg.sender;
        issuers[msg.sender] = true;
        emit IssuerUpdated(msg.sender, true);
    }

    function setIssuer(address issuer, bool isAuthorized) external onlyOwner {
        require(issuer != address(0), "Invalid issuer");
        issuers[issuer] = isAuthorized;
        emit IssuerUpdated(issuer, isAuthorized);
    }

    function issueCertificate(bytes32 certificateHash, address studentWallet) external onlyIssuer {
        require(studentWallet != address(0), "Invalid student wallet");
        require(!certificates[certificateHash].exists, "Certificate already sealed");

        certificates[certificateHash] = CertificateRecord({
            issuer: msg.sender,
            studentWallet: studentWallet,
            issuedAt: block.timestamp,
            exists: true
        });

        emit CertificateIssued(certificateHash, msg.sender, studentWallet, block.timestamp);
    }

    function verifyCertificate(bytes32 certificateHash)
        external
        view
        returns (bool isVerified, address issuer, address studentWallet, uint256 issuedAt)
    {
        CertificateRecord memory record = certificates[certificateHash];
        if (!record.exists) {
            return (false, address(0), address(0), 0);
        }

        return (true, record.issuer, record.studentWallet, record.issuedAt);
    }
}
