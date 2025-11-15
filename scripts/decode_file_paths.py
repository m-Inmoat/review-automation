#!/usr/bin/env python3
import os
import sys
import re

def decode_file_path(file_path: str) -> str:
    """
    単一のファイルパスをデコード
    
    Git の8進数エスケープ（例: \\346\\217\\220）をUTF-8文字に変換し、
    パス区切りのバックスラッシュをスラッシュに正規化します。
    エスケープされていない日本語が混在する場合も適切に処理します。
    
    Args:
        file_path: エスケープされた可能性のあるファイルパス
    
    Returns:
        デコードされたファイルパス
    """
    if not file_path:
        return file_path
    
    try:
        # まず8進数エスケープシーケンスがあるかチェック
        pattern = r'\\(\d{3})'
        has_octal_escape = bool(re.search(pattern, file_path))
        
        if has_octal_escape:
            # 8進数エスケープが含まれる場合：従来の処理
            byte_parts = []
            last_end = 0
            
            for match in re.finditer(pattern, file_path):
                # マッチ前の通常文字列を追加
                byte_parts.append(file_path[last_end:match.start()].encode('utf-8'))
                # 8進数をバイトに変換
                octal_value = int(match.group(1), 8)
                byte_parts.append(bytes([octal_value]))
                last_end = match.end()
            
            # 残りの文字列を追加
            byte_parts.append(file_path[last_end:].encode('utf-8'))
            
            # バイト列を結合してUTF-8デコード
            full_bytes = b''.join(byte_parts)
            decoded = full_bytes.decode('utf-8', errors='replace')
            
            # パス区切りのバックスラッシュをスラッシュに正規化
            normalized = decoded.replace('\\', '/')
        else:
            # 8進数エスケープがない場合：quotepath無視されたケース
            # \提\出 のような日本語間のバックスラッシュを除去
            # 通常のパス区切り（英数字/記号の後の\）は / に変換
            
            # 日本語文字の直後のバックスラッシュを一時的にマーカーに置換
            temp = file_path
            # 非ASCII文字の直前と直後の \ を特殊マーカーに置換
            # 前方参照：非ASCII文字の後の\
            temp = re.sub(r'([^\x00-\x7f])\\', r'\1<<<REMOVE>>>', temp)
            # 後方参照：非ASCII文字の前の\
            temp = re.sub(r'\\([^\x00-\x7f])', r'<<<REMOVE>>>\1', temp)
            # 残ったバックスラッシュをスラッシュに変換（パス区切り）
            temp = temp.replace('\\', '/')
            # マーカーを削除（日本語間の不要な区切りを除去）
            normalized = temp.replace('<<<REMOVE>>>', '')
        
        return normalized
    except Exception as e:
        # デコードに失敗した場合は、バックスラッシュを正規化して返す
        print(f"Info: Decode failed for '{file_path}': {e}", file=sys.stderr)
        normalized = file_path.replace('\\', '/')
        print(f"Info: Using normalized path: '{normalized}'", file=sys.stderr)
        return normalized


def decode_file_paths(raw_files_string, output_file='decoded_files.txt'):
    """
    エスケープされたファイルパス文字列をデコードしてファイルに出力
    
    Args:
        raw_files_string: カンマ区切りのファイルパス文字列
        output_file: 出力ファイル名（デフォルト: decoded_files.txt）
    """
    if not raw_files_string:
        print("No files to decode", file=sys.stderr)
        sys.exit(0)
    
    # カンマで区切ってファイルリストを作成
    files = []
    for f in raw_files_string.split(','):
        f = f.strip()
        if f:
            files.append(decode_file_path(f))
    
    # デコードされたファイルリストを出力
    if files:
        with open(output_file, 'w', encoding='utf-8') as out:
            for f in files:
                out.write(f + '\n')
        print(f"Successfully decoded {len(files)} file(s)", file=sys.stderr)
        for f in files:
            print(f"  - {f}", file=sys.stderr)
    else:
        print("No files after decoding", file=sys.stderr)

def main():
    # 環境変数から変更されたファイルの一覧を取得
    raw = os.environ.get('CHANGED_FILES_RAW', '')
    decode_file_paths(raw)

if __name__ == "__main__":
    main()
