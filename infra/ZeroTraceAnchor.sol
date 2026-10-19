// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.20;

/**
 * @title ZeroTraceAnchor
 * @dev Autonomous On-Chain Tamper-Evident Ledger for India's DPDP Act, 2023 Compliance Receipts.
 * Anchors Merkle diff roots and emits immutable verifiable event logs.
 */
contract ZeroTraceAnchor {
    address public immutable owner;

    struct AnchorRecord {
        bytes32 diffRoot;
        string receiptId;
        uint256 timestamp;
        uint256 blockNumber;
    }

    // Mapping from receiptId to AnchorRecord
    mapping(string => AnchorRecord) public records;

    // Mapping from diffRoot to existence bool
    mapping(bytes32 => bool) public anchoredRoots;

    event RootAnchored(
        bytes32 indexed diffRoot,
        string indexed receiptId,
        uint256 timestamp,
        uint256 blockNumber
    );

    error NotAuthorized();
    error AlreadyAnchored();
    error InvalidRoot();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotAuthorized();
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @notice Anchor a ZeroTrace Merkle diff root on-chain.
     * @param diffRoot 32-byte salted Merkle root of destroyed/held storage items.
     * @param receiptId Canonical ULID receipt identifier (e.g. rcpt_01JB...).
     */
    function anchorRoot(bytes32 diffRoot, string calldata receiptId) external onlyOwner {
        if (diffRoot == bytes32(0)) revert InvalidRoot();
        if (records[receiptId].timestamp != 0) revert AlreadyAnchored();

        records[receiptId] = AnchorRecord({
            diffRoot: diffRoot,
            receiptId: receiptId,
            timestamp: block.timestamp,
            blockNumber: block.number
        });

        anchoredRoots[diffRoot] = true;

        emit RootAnchored(diffRoot, receiptId, block.timestamp, block.number);
    }

    /**
     * @notice Verify whether a diff root has been anchored on-chain.
     */
    function isRootAnchored(bytes32 diffRoot) external view returns (bool) {
        return anchoredRoots[diffRoot];
    }

    /**
     * @notice Retrieve the full anchor record for a receipt ID.
     */
    function getRecord(string calldata receiptId) external view returns (AnchorRecord memory) {
        return records[receiptId];
    }
}
