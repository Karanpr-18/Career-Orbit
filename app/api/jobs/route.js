import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
import fs from 'fs';
import path from 'path';
import Papa from 'papaparse';

const CSV_PATH = process.env.TRACKER_CSV_PATH || path.join(process.cwd(), 'tracker.csv');

function getCsvData() {
  if (!fs.existsSync(CSV_PATH)) {
    return [];
  }
  const fileContent = fs.readFileSync(CSV_PATH, 'utf-8');
  
  const results = Papa.parse(fileContent, {
    header: true,
    skipEmptyLines: true,
    transformHeader: (header) => header.replace(/^['"]+|['"]+$/g, '').trim(),
    transform: (value) => value.replace(/^['"]+|['"]+$/g, '').trim(),
  });

  let data = results.data;
  let dataModified = false;

  // Ensure 'Application Status' column exists
  data = data.map(row => {
    if (!row['Application Status']) {
      row['Application Status'] = 'Mailed';
      dataModified = true;
    }
    return row;
  });

  if (dataModified) {
    saveCsvData(data);
  }

  return data;
}

function saveCsvData(data) {
  // Use Papa.unparse with consistent single quotes to match original style
  const csv = Papa.unparse(data, {
    quotes: true,
    quoteChar: "'",
  });
  fs.writeFileSync(CSV_PATH, csv, 'utf-8');
}

export async function GET() {
  try {
    const data = getCsvData();
    return NextResponse.json({ success: true, data });
  } catch (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function POST(request) {
  try {
    const body = await request.json();
    const { rowIndex, status } = body;

    const data = getCsvData();
    if (rowIndex >= 0 && rowIndex < data.length) {
      data[rowIndex]['Application Status'] = status;
      saveCsvData(data);
      return NextResponse.json({ success: true, data });
    } else {
      return NextResponse.json({ success: false, error: 'Invalid row index' }, { status: 400 });
    }
  } catch (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function DELETE(request) {
  try {
    const body = await request.json();
    const { rowIndex } = body;

    const data = getCsvData();
    if (rowIndex >= 0 && rowIndex < data.length) {
      data.splice(rowIndex, 1);
      saveCsvData(data);
      return NextResponse.json({ success: true, data });
    } else {
      return NextResponse.json({ success: false, error: 'Invalid row index' }, { status: 400 });
    }
  } catch (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
