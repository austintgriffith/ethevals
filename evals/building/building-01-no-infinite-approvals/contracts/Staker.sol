// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/// Minimal USDC staking: deposit any amount, withdraw the whole position. No rewards.
contract Staker {
    using SafeERC20 for IERC20;

    IERC20 public immutable usdc;
    mapping(address => uint256) public staked;

    event Staked(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);

    constructor(IERC20 _usdc) {
        usdc = _usdc;
    }

    /// Caller must have approved this contract for at least `amount` first.
    function stake(uint256 amount) external {
        require(amount > 0, "zero amount");
        staked[msg.sender] += amount;
        usdc.safeTransferFrom(msg.sender, address(this), amount);
        emit Staked(msg.sender, amount);
    }

    function withdraw() external {
        uint256 amount = staked[msg.sender];
        require(amount > 0, "nothing staked");
        staked[msg.sender] = 0;
        usdc.safeTransfer(msg.sender, amount);
        emit Withdrawn(msg.sender, amount);
    }
}
