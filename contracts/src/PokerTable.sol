// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title PokerTable - Multi-player escrow for TEE-verified poker
/// @notice Players deposit ETH to play. The operator (TEE enclave) settles
///         each hand by transferring chips between player balances on-chain.
///         Players can withdraw their balance between hands.
contract PokerTable {
    address public immutable operator;
    uint256 public immutable smallBlind;
    uint256 public immutable bigBlind;
    uint256 public immutable minBuyIn;
    uint256 public immutable maxBuyIn;
    uint8 public immutable maxSeats;

    mapping(address => uint256) public balances;
    address[] public players;
    mapping(address => bool) public isSeated;

    uint256 public lastSettledHand;
    mapping(uint256 => bytes32) public handResultHashes;

    bool public isOpen;
    bool private _locked;

    event PlayerDeposited(address indexed player, uint256 amount);
    event PlayerWithdrew(address indexed player, uint256 amount);
    event HandSettled(uint256 indexed handNumber, bytes32 resultHash);
    event TableClosed();

    modifier onlyOperator() {
        require(msg.sender == operator, "Only operator");
        _;
    }

    modifier tableOpen() {
        require(isOpen, "Table closed");
        _;
    }

    modifier nonReentrant() {
        require(!_locked, "Reentrant");
        _locked = true;
        _;
        _locked = false;
    }

    constructor(
        address _operator,
        uint256 _smallBlind,
        uint256 _bigBlind,
        uint256 _minBuyIn,
        uint256 _maxBuyIn,
        uint8 _maxSeats
    ) {
        require(_operator != address(0), "Invalid operator");
        require(_bigBlind > _smallBlind, "BB must exceed SB");
        require(_minBuyIn >= _bigBlind * 10, "Min buy-in too low");
        require(_maxBuyIn >= _minBuyIn, "Max must exceed min");
        require(_maxSeats >= 2 && _maxSeats <= 9, "Invalid seat count");

        operator = _operator;
        smallBlind = _smallBlind;
        bigBlind = _bigBlind;
        minBuyIn = _minBuyIn;
        maxBuyIn = _maxBuyIn;
        maxSeats = _maxSeats;
        isOpen = true;
    }

    /// @notice Deposit ETH to sit at the table
    function deposit() external payable tableOpen nonReentrant {
        require(msg.value >= minBuyIn || balances[msg.sender] > 0, "Below min buy-in");
        require(balances[msg.sender] + msg.value <= maxBuyIn, "Exceeds max buy-in");

        if (!isSeated[msg.sender]) {
            require(players.length < maxSeats, "Table full");
            players.push(msg.sender);
            isSeated[msg.sender] = true;
        }

        balances[msg.sender] += msg.value;
        emit PlayerDeposited(msg.sender, msg.value);
    }

    /// @notice Withdraw all remaining balance
    function withdraw() external nonReentrant {
        uint256 bal = balances[msg.sender];
        require(bal > 0, "No balance");

        balances[msg.sender] = 0;
        isSeated[msg.sender] = false;
        _removePlayer(msg.sender);

        emit PlayerWithdrew(msg.sender, bal);
        (bool ok,) = msg.sender.call{value: bal}("");
        require(ok, "Transfer failed");
    }

    /// @notice Settle a hand: transfer chips between players (operator only)
    /// @dev Zero-sum enforced: total won must equal total lost
    function settleHand(
        uint256 handNumber,
        bytes32 resultHash,
        address[] calldata winners,
        uint256[] calldata amounts,
        address[] calldata losers,
        uint256[] calldata losses
    ) external onlyOperator nonReentrant {
        require(handNumber == lastSettledHand + 1, "Wrong hand number");
        require(winners.length == amounts.length, "Winner length mismatch");
        require(losers.length == losses.length, "Loser length mismatch");

        uint256 totalWon;
        uint256 totalLost;
        for (uint256 i = 0; i < amounts.length; i++) totalWon += amounts[i];
        for (uint256 i = 0; i < losses.length; i++) totalLost += losses[i];
        require(totalWon == totalLost, "Not zero-sum");

        for (uint256 i = 0; i < losers.length; i++) {
            require(balances[losers[i]] >= losses[i], "Insufficient balance");
            balances[losers[i]] -= losses[i];
        }

        for (uint256 i = 0; i < winners.length; i++) {
            balances[winners[i]] += amounts[i];
        }

        handResultHashes[handNumber] = resultHash;
        lastSettledHand = handNumber;
        emit HandSettled(handNumber, resultHash);
    }

    /// @notice Close the table (operator only)
    function closeTable() external onlyOperator {
        isOpen = false;
        emit TableClosed();
    }

    /// @notice Emergency withdraw after table is closed
    function emergencyWithdraw() external nonReentrant {
        require(!isOpen, "Table still open");
        uint256 bal = balances[msg.sender];
        require(bal > 0, "No balance");
        balances[msg.sender] = 0;
        (bool ok,) = msg.sender.call{value: bal}("");
        require(ok, "Transfer failed");
    }

    /// @notice Verify a hand result hash
    function verifyHandResult(uint256 handNumber, bytes32 expectedHash) external view returns (bool) {
        return handResultHashes[handNumber] == expectedHash;
    }

    function getPlayerCount() external view returns (uint256) { return players.length; }
    function getBalance(address player) external view returns (uint256) { return balances[player]; }

    function _removePlayer(address player) internal {
        for (uint256 i = 0; i < players.length; i++) {
            if (players[i] == player) {
                players[i] = players[players.length - 1];
                players.pop();
                break;
            }
        }
    }
}
